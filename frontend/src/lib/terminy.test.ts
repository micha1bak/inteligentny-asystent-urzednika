import { describe, expect, it } from 'vitest';
import { czyDzienWolny, maksDniKwerendy, pilnosc, porownajWgCzasuNaOdpowiedz, terminOdpowiedzi } from './terminy';
import type { Wniosek } from '../types';

const wniosek = (p: Partial<Wniosek>): Wniosek => ({
  id: 'x', numer: 'BKS.IV.1431.1.2026', dataWplywu: '2026-11-02', temat: '', wnioskodawca: '',
  inicjaly: '', tresc: '', status: 'brak_dzialan', ...p,
});

describe('terminy UDIP', () => {
  it('liczy 14 dni od dnia po wpływie', () => {
    expect(terminOdpowiedzi({ dataWplywu: '2026-11-02' })).toBe('2026-11-16');
  });

  it('przesuwa termin z soboty na poniedziałek', () => {
    // 2026-11-07 + 14 = 2026-11-21 (sobota) -> 2026-11-23
    expect(terminOdpowiedzi({ dataWplywu: '2026-11-07' })).toBe('2026-11-23');
  });

  it('przesuwa termin z dnia ustawowo wolnego', () => {
    // 2026-10-28 + 14 = 2026-11-11 (Święto Niepodległości, środa) -> 2026-11-12
    expect(terminOdpowiedzi({ dataWplywu: '2026-10-28' })).toBe('2026-11-12');
  });

  it('uwzględnia Wigilię jako dzień wolny od 2025 r. i święta ruchome', () => {
    expect(czyDzienWolny('2025-12-24')).toBe(true);
    expect(czyDzienWolny('2026-04-06')).toBe(true); // poniedziałek wielkanocny 2026
    expect(czyDzienWolny('2026-06-04')).toBe(true); // Boże Ciało 2026
  });

  it('dodaje dni kwerendy, ale nie dalej niż 2 miesiące od wpływu', () => {
    expect(terminOdpowiedzi({ dataWplywu: '2026-11-02', dniKwerendy: 14 })).toBe('2026-11-30');
    expect(terminOdpowiedzi({ dataWplywu: '2026-11-02', dniKwerendy: 200 })).toBe('2027-01-04'); // 2.01 to sobota
    expect(maksDniKwerendy('2026-11-02')).toBe(47);
  });

  it('oznacza pilność', () => {
    expect(pilnosc(wniosek({}), '2026-11-16').pilnosc).toBe('dzis');
    expect(pilnosc(wniosek({}), '2026-11-15').pilnosc).toBe('jutro');
    // piątek i sobota przed terminem poniedziałkowym (16.11.2026) – „następny dzień roboczy”
    expect(pilnosc(wniosek({}), '2026-11-13').pilnosc).toBe('jutro');
    expect(pilnosc(wniosek({}), '2026-11-14').pilnosc).toBe('jutro');
    expect(pilnosc(wniosek({}), '2026-11-12').pilnosc).toBe('w_terminie'); // czwartek – 4 dni
    expect(pilnosc(wniosek({}), '2026-11-17').pilnosc).toBe('po_terminie');
    expect(pilnosc(wniosek({ status: 'odpowiedz_wyslana' }), '2026-11-17').pilnosc).toBe('zakonczony');
  });
});

describe('kolejność listy wniosków', () => {
  it('najmniej czasu na odpowiedź na górze, wysłane na końcu', () => {
    const w = [
      { numer: 'A', status: 'brak_dzialan' as const, termin: '2026-11-30', dataWplywu: '2026-11-16' },
      { numer: 'B', status: 'odpowiedz_wyslana' as const, termin: '2026-11-10', dataWplywu: '2026-10-27' },
      { numer: 'C', status: 'kwerenda' as const, termin: '2026-11-20', dataWplywu: '2026-11-01' },
      { numer: 'D', status: 'brak_dzialan' as const, termin: '2026-11-24', dataWplywu: '2026-11-10' },
    ];
    expect([...w].sort(porownajWgCzasuNaOdpowiedz).map((x) => x.numer)).toEqual(['C', 'D', 'A', 'B']);
  });
});
