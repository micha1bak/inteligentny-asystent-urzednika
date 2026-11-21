import { describe, expect, it } from 'vitest';
import { dodajUkrycie, podzielNaUkrycia, przelaczUkrycie, scalSugestie, zastosujUkrycia, type Ukrycie } from './anonimizacja';

const U: Ukrycie[] = [
  { tekst: 'Jan Kowalski', rodzaj: 'imię i nazwisko', stan: 'ukryte' },
  { tekst: 'ul. Lipowa 7', rodzaj: 'adres', stan: 'proponowane' },
  { tekst: 'Kowalski', rodzaj: 'wskazane', stan: 'proponowane' },
];

describe('anonimizacja', () => {
  it('dzieli tekst na odcinki, dłuższa fraza wygrywa', () => {
    const o = podzielNaUkrycia('Jan Kowalski, ul. Lipowa 7. Kowalski.', U);
    expect(o.map((x) => [x.tekst, x.ukrycie?.stan ?? null])).toEqual([
      ['Jan Kowalski', 'ukryte'], [', ', null], ['ul. Lipowa 7', 'proponowane'], ['. ', null], ['Kowalski', 'proponowane'], ['.', null],
    ]);
  });
  it('zastępuje tylko ukryte fragmenty, każde wystąpienie', () => {
    expect(zastosujUkrycia('Jan Kowalski i Jan Kowalski, ul. Lipowa 7', U)).toBe('████████████ i ████████████, ul. Lipowa 7');
  });
  it('scala sugestie z decyzjami urzędnika', () => {
    const s = scalSugestie(U, [
      { tekst: 'Jan Kowalski', rodzaj: 'imię i nazwisko', start: 0, koniec: 12 },
      { tekst: '600 123 456', rodzaj: 'numer telefonu', start: 0, koniec: 11 },
      { tekst: 'odrzucone', rodzaj: 'x', start: 0, koniec: 9 },
    ], ['odrzucone']);
    expect(s.find((u) => u.tekst === 'Jan Kowalski')?.stan).toBe('ukryte');
    expect(s.find((u) => u.tekst === '600 123 456')?.stan).toBe('proponowane');
    expect(s.some((u) => u.tekst === 'odrzucone')).toBe(false);
  });
  it('przełącza i dodaje ukrycia', () => {
    expect(przelaczUkrycie(U, 'ul. Lipowa 7').find((u) => u.tekst === 'ul. Lipowa 7')?.stan).toBe('ukryte');
    expect(przelaczUkrycie(U, 'Jan Kowalski').find((u) => u.tekst === 'Jan Kowalski')?.stan).toBe('proponowane');
    expect(dodajUkrycie(U, '  85-001 Bydgoszcz ').at(-1)).toEqual({ tekst: '85-001 Bydgoszcz', rodzaj: 'zaznaczone', stan: 'ukryte' });
    expect(dodajUkrycie(U, 'x')).toBe(U);
  });
});
