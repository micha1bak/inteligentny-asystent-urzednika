import { describe, expect, it } from 'vitest';
import { dodajReczny, poprawnyPesel, przesunPoEdycji, wykryj, zastosuj } from './anonimizacja';

const WNIOSEK = `Aleksandra Wójcik-Nowak
ul. Długa 15 m. 4
85-034 Bydgoszcz
PESEL: 44051401359
seria i nr dowodu: ABC 123456
tel. +48 601 234 567
e-mail: a.wojcik.nowak@example.com
nr rachunku: PL61 1090 1014 0000 0712 1981 2874
czy mój sąsiad, pan Roman Kowalczyk zamieszkały przy ul. Długiej 17, otrzymał pozwolenie`;

const wartosci = (t: string) => wykryj(t).map((f) => [f.kategoria, t.slice(f.start, f.koniec)]);

describe('wykrywanie danych osobowych', () => {
  it('sprawdza sumę kontrolną PESEL', () => {
    expect(poprawnyPesel('44051401359')).toBe(true);
    expect(poprawnyPesel('44051401358')).toBe(false);
  });

  it('znajduje wszystkie dane z przykładowego wniosku', () => {
    const w = wartosci(WNIOSEK);
    expect(w).toContainEqual(['Imię i nazwisko', 'Aleksandra Wójcik-Nowak']);
    expect(w).toContainEqual(['Adres zamieszkania', 'ul. Długa 15 m. 4']);
    expect(w).toContainEqual(['Adres zamieszkania', '85-034 Bydgoszcz']);
    expect(w).toContainEqual(['PESEL', '44051401359']);
    expect(w).toContainEqual(['Dokument tożsamości', 'ABC 123456']);
    expect(w).toContainEqual(['Numer telefonu', '+48 601 234 567']);
    expect(w).toContainEqual(['Adres e-mail', 'a.wojcik.nowak@example.com']);
    expect(w).toContainEqual(['Numer rachunku bankowego', 'PL61 1090 1014 0000 0712 1981 2874']);
    expect(w).toContainEqual(['Imię i nazwisko', 'Roman Kowalczyk']);
    expect(w).toContainEqual(['Adres zamieszkania', 'ul. Długiej 17']);
  });

  it('nie zaznacza zwykłych liczb i kwot', () => {
    expect(wykryj('Koszt wyniósł 12 300 000 zł, w 2026 r. 839 psów.')).toEqual([]);
  });
});

describe('stosowanie anonimizacji', () => {
  it('zastępuje tylko zaakceptowane fragmenty', () => {
    const tekst = 'Kontakt: jan@example.com, tel. 600 123 456';
    const f = wykryj(tekst);
    f[0].stan = 'zaakceptowany';
    expect(zastosuj(tekst, f)).toBe('Kontakt: [dane zanonimizowane], tel. 600 123 456');
  });

  it('ręczne zaznaczenie zastępuje nakładające się propozycje', () => {
    const tekst = 'Pan Roman Kowalczyk mieszka obok';
    const f = dodajReczny(wykryj(tekst), 0, 19);
    expect(f).toHaveLength(1);
    expect(zastosuj(tekst, f)).toBe('[dane zanonimizowane] mieszka obok');
  });

  it('przesuwa fragmenty po edycji tekstu przed nimi', () => {
    const stary = 'Tel. 600 123 456';
    const f = wykryj(stary);
    const nowy = 'Numer tel. 600 123 456';
    const [p] = przesunPoEdycji(stary, nowy, f);
    expect(nowy.slice(p.start, p.koniec)).toBe('600 123 456');
  });
});
