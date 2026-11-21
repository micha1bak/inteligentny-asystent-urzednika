import { describe, expect, it } from 'vitest';
import {
  fragmentyZnacznikow, pismoNaTekst, przeniesZakres, przesunBlok, rozlozNaStrony, usunBlok, wstawBlok, zakresBloku,
  type BlokPisma, type StrukturaPisma,
} from './pismo';

const PISMO: StrukturaPisma = {
  naglowek: ['URZĄD MIASTA BYDGOSZCZY', 'Biuro Komunikacji Społecznej'],
  data: 'Bydgoszcz, dnia 21 listopada 2026 r.',
  znak: 'BKS.IV.1431.18.2026',
  adresat: [],
  tytul: [],
  tresc: [
    { typ: 'zwrot', tekst: 'Szanowny Panie,' },
    { typ: 'akapit', tekst: 'w odpowiedzi … informuję, że 5697 osób.' },
  ],
  zakonczenie: 'Łączę wyrazy szacunku,',
  podpis: ['Biuro Komunikacji Społecznej', 'Urząd Miasta Bydgoszczy'],
  stopka: ['85-102 Bydgoszcz, ul. Jezuicka 1'],
};

describe('pismoNaTekst', () => {
  it('składa linie w kolejności pisma, stopka po pustej linii', () => {
    expect(pismoNaTekst(PISMO).split('\n')).toEqual([
      'URZĄD MIASTA BYDGOSZCZY',
      'Biuro Komunikacji Społecznej',
      'Bydgoszcz, dnia 21 listopada 2026 r.',
      'BKS.IV.1431.18.2026',
      'Szanowny Panie,',
      'w odpowiedzi … informuję, że 5697 osób.',
      'Łączę wyrazy szacunku,',
      'Biuro Komunikacji Społecznej',
      'Urząd Miasta Bydgoszczy',
      '',
      '85-102 Bydgoszcz, ul. Jezuicka 1',
    ]);
  });
});

describe('rozlozNaStrony', () => {
  const h = (...w: number[]) => w.map((wysokosc) => ({ wysokosc }));
  // akapit: 10 jednostek wysokości na każde rozpoczęte 3 słowa (linia = 3 słowa)
  const mierz = (slowa: string[]) => Math.ceil(slowa.length / 3) * 10;
  const akapit = (n: number) => {
    const slowa = Array.from({ length: n }, (_, i) => `s${i}`);
    return { wysokosc: mierz(slowa), slowa };
  };

  it('przenosi element, który się nie mieści, na kolejną stronę', () => {
    expect(rozlozNaStrony(h(40, 40, 30, 50), 100)).toEqual([[{ i: 0 }, { i: 1 }], [{ i: 2 }, { i: 3 }]]);
  });
  it('element wyższy od strony dostaje własną stronę', () => {
    expect(rozlozNaStrony(h(20, 150, 20), 100)).toEqual([[{ i: 0 }], [{ i: 1 }], [{ i: 2 }]]);
  });
  it('pusta lista to jedna pusta strona', () => {
    expect(rozlozNaStrony([], 100)).toEqual([[]]);
  });
  it('dzieli akapit po słowach między strony', () => {
    // 70 zajęte, akapit 18 słów = 60 wysokości; mieszczą się 3 linie (9 słów) = 30
    expect(rozlozNaStrony([...h(70), akapit(18)], 100, mierz, 20)).toEqual([
      [{ i: 0 }, { i: 1, od: 0, do: 9 }],
      [{ i: 1, od: 9, do: 18 }],
    ]);
  });
  it('nie dzieli, gdy zostało mniej niż minimum', () => {
    expect(rozlozNaStrony([...h(85), akapit(18)], 100, mierz, 20)).toEqual([[{ i: 0 }], [{ i: 1 }]]);
  });
  it('„Ad n” nie zostaje sam na dole strony', () => {
    // Ad (10) zmieściłby się, ale po nim nie ma miejsca na 2 linie akapitu
    expect(rozlozNaStrony([...h(80), { wysokosc: 10, trzymajZNastepnym: true }, akapit(12)], 100, mierz, 20)).toEqual([
      [{ i: 0 }],
      [{ i: 1 }, { i: 2 }],
    ]);
  });
});

describe('fragmentyZnacznikow', () => {
  it('wyodrębnia znaczniki [[…]]', () => {
    expect(fragmentyZnacznikow('że [[do uzupełnienia: liczba]] osób.')).toEqual([
      { tekst: 'że ', znacznik: false },
      { tekst: '[[do uzupełnienia: liczba]]', znacznik: true },
      { tekst: ' osób.', znacznik: false },
    ]);
  });
});

describe('przestawianie bloków', () => {
  const l = ['a', 'b', 'c', 'd'];
  it('przenosi pojedynczy blok w dół i w górę', () => {
    expect(przeniesZakres(l, 0, 1, 3)).toEqual(['b', 'c', 'a', 'd']);
    expect(przeniesZakres(l, 3, 4, 1)).toEqual(['a', 'd', 'b', 'c']);
    expect(przeniesZakres(l, 1, 2, 4)).toEqual(['a', 'c', 'd', 'b']);
  });
  it('upuszczenie w tym samym miejscu lub poza listą niczego nie zmienia', () => {
    expect(przeniesZakres(l, 1, 2, 1)).toBe(l);
    expect(przeniesZakres(l, 1, 2, 2)).toBe(l);
    expect(przeniesZakres(l, 1, 2, 9)).toBe(l);
  });
  it('usuwa i wstawia', () => {
    expect(usunBlok(l, 1)).toEqual(['a', 'c', 'd']);
    expect(wstawBlok(l, 1, 'x')).toEqual(['a', 'b', 'x', 'c', 'd']);
  });
});

describe('grupy „Ad n” z odpowiedziami', () => {
  const b = (typ: BlokPisma['typ'], tekst: string): BlokPisma => ({ typ, tekst });
  const tresc = [
    b('akapit', 'wstęp'), b('ad', 'Ad 1'), b('akapit', 'o1'), b('ad', 'Ad 2'), b('akapit', 'o2a'), b('akapit', 'o2b'),
    b('ad', 'Ad 3'), b('akapit', 'o3'), b('linia', 'Załączniki:'),
  ];
  const teksty = (l: BlokPisma[]) => l.map((x) => x.tekst);

  it('„Ad n” obejmuje akapity odpowiedzi, zwykły blok – tylko siebie', () => {
    expect(zakresBloku(tresc, 3)).toEqual([3, 6]);
    expect(zakresBloku(tresc, 6)).toEqual([6, 8]); // bez linii „Załączniki:”
    expect(zakresBloku(tresc, 4)).toEqual([4, 5]);
  });
  it('przenosi całą grupę przeciąganiem', () => {
    expect(teksty(przeniesZakres(tresc, 6, 8, 1))).toEqual(['wstęp', 'Ad 3', 'o3', 'Ad 1', 'o1', 'Ad 2', 'o2a', 'o2b', 'Załączniki:']);
    expect(przeniesZakres(tresc, 3, 6, 4)).toBe(tresc); // upuszczenie wewnątrz własnej grupy
  });
  it('↑ / ↓ przy „Ad n” zamienia całe grupy', () => {
    expect(teksty(przesunBlok(tresc, 3, -1))).toEqual(['wstęp', 'Ad 2', 'o2a', 'o2b', 'Ad 1', 'o1', 'Ad 3', 'o3', 'Załączniki:']);
    expect(teksty(przesunBlok(tresc, 3, 1))).toEqual(['wstęp', 'Ad 1', 'o1', 'Ad 3', 'o3', 'Ad 2', 'o2a', 'o2b', 'Załączniki:']);
  });
  it('↑ / ↓ przy zwykłym akapicie przesuwa jeden blok', () => {
    expect(teksty(przesunBlok(tresc, 5, -1)).slice(3, 6)).toEqual(['Ad 2', 'o2b', 'o2a']);
    expect(przesunBlok(tresc, 0, -1)).toBe(tresc);
  });
});
