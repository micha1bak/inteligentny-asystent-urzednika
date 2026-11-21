import type { Jednostka, SprawaArchiwalna } from '../types';
import { szukajPodobnych } from './podobienstwo';

export interface Propozycja {
  jednostka: Jednostka;
  wynik: number;
  powody: string[];
}

/**
 * Podpowiada wydziały/biura: dopasowanie treści wniosku do zakresu jednostki
 * plus "głos" komórek, które odpowiadały na najbardziej podobne sprawy archiwalne.
 */
export function proponujWydzialy(
  tresc: string,
  jednostki: Jednostka[],
  archiwum: SprawaArchiwalna[],
  limit = 4,
): Propozycja[] {
  const punkty = new Map<string, Propozycja>();
  const dodaj = (j: Jednostka, wynik: number, powod: string) => {
    const p = punkty.get(j.symbol) ?? { jednostka: j, wynik: 0, powody: [] };
    p.wynik += wynik;
    p.powody.push(powod);
    punkty.set(j.symbol, p);
  };

  // pomijamy biuro prowadzące wnioski (BKS) – ono koordynuje, nie przygotowuje merytorycznie
  const kandydaci = jednostki.filter((j) => j.symbol !== 'BKS');
  const zakres = szukajPodobnych(
    tresc,
    kandydaci.map((j) => ({ element: j, tekst: `${j.nazwa} ${j.zakres}` })),
    limit + 2,
  );
  for (const r of zakres) dodaj(r.element, r.wynik, `zakres: ${r.wspolne.slice(0, 3).join(', ')}…`);

  const podobne = szukajPodobnych(
    tresc,
    archiwum.map((a) => ({ element: a, tekst: `${a.wniosek} ${a.odpowiedz}` })),
    3,
  );
  for (const r of podobne) {
    const j = kandydaci.find((x) => r.element.komorka.toLowerCase().includes(x.nazwa.toLowerCase()));
    if (j) dodaj(j, r.wynik * 0.8, `podobna sprawa ${r.element.sygnatura}`);
  }

  return [...punkty.values()].sort((a, b) => b.wynik - a.wynik).slice(0, limit);
}
