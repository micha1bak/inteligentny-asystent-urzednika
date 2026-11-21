import type { Fragment } from '../types';

/**
 * Wykrywanie danych podlegających anonimizacji (katalog 28 kategorii – tu te, które da się
 * rozpoznać regułami). To tylko PROPOZYCJA: urzędnik akceptuje, odrzuca lub dopisuje fragmenty.
 * Docelowo backend uzupełni to o model NER uruchamiany lokalnie.
 */

interface Regula {
  kategoria: string;
  wzorzec: RegExp;
  /** dodatkowa walidacja dopasowania (np. suma kontrolna PESEL) */
  sprawdz?: (dopasowanie: string) => boolean;
  /** numer grupy z właściwą wartością (domyślnie całe dopasowanie) */
  grupa?: number;
}

const IMIONA =
  'Adam Agnieszka Aleksandra Aleksander Alicja Andrzej Anna Barbara Bartosz Beata Dariusz Dawid Dorota Edyta Elżbieta Emilia Ewa Grzegorz Halina Hanna Ilona Irena Jacek Jakub Jan Janina Jarosław Joanna Jolanta Józef Julia Justyna Kamil Karol Karolina Katarzyna Kazimierz Krystyna Krzysztof Łukasz Maciej Magdalena Małgorzata Marcin Marek Maria Mariusz Marta Mateusz Michał Monika Natalia Paweł Piotr Rafał Renata Robert Roman Ryszard Sebastian Stanisław Stefan Sylwia Szymon Tadeusz Teresa Tomasz Urszula Wiesław Wiktoria Wojciech Zbigniew Zofia Zuzanna'.split(
    ' ',
  );

const DUZA = '\\p{Lu}\\p{Ll}+';
const NAZWISKO = `${DUZA}(?:-${DUZA})?`;

const REGULY: Regula[] = [
  { kategoria: 'PESEL', wzorzec: /\b\d{11}\b/g, sprawdz: poprawnyPesel },
  { kategoria: 'Numer rachunku bankowego', wzorzec: /\b(?:PL ?)?\d{2}(?: ?\d{4}){6}\b/g },
  { kategoria: 'Dokument tożsamości', wzorzec: /\b[A-Z]{3} ?\d{6}\b/g },
  { kategoria: 'Adres e-mail', wzorzec: /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g },
  {
    kategoria: 'Numer telefonu',
    wzorzec: /(?:\+48[ -]?)?\b\d{3}[ -]\d{3}[ -]\d{3}\b|\b\d{2} \d{3} \d{2} \d{2}\b/g,
  },
  {
    kategoria: 'Adres zamieszkania',
    wzorzec: new RegExp(`\\b(?:ul\\.|al\\.|os\\.|pl\\.) ?${DUZA}(?: ${DUZA})*\\.? \\d+[a-zA-Z]?(?:(?: ?m\\.? ?| ?/ ?)\\d+)?`, 'gu'),
  },
  { kategoria: 'Adres zamieszkania', wzorzec: /\b\d{2}-\d{3} \p{Lu}\p{Ll}+/gu },
  { kategoria: 'Numer księgi wieczystej', wzorzec: /\b[A-Z]{2}\d[A-Z]\/\d{8}\/\d\b/g },
  { kategoria: 'Numer NIP', wzorzec: /\bNIP:? ?(\d{3}-?\d{3}-?\d{2}-?\d{2})\b/g, grupa: 1 },
  {
    kategoria: 'Data urodzenia',
    wzorzec: /(?:urodzon[aey]|ur\.)\s+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})/g,
    grupa: 1,
  },
  {
    kategoria: 'Imię i nazwisko',
    wzorzec: new RegExp(`\\b(?:${IMIONA.join('|')}) ${NAZWISKO}`, 'gu'),
  },
  {
    kategoria: 'Imię i nazwisko',
    wzorzec: new RegExp(`\\b(?:pan|pani|panu|panią|pana)\\s+(${DUZA} ${NAZWISKO})`, 'gu'),
    grupa: 1,
  },
];

export function poprawnyPesel(p: string): boolean {
  if (!/^\d{11}$/.test(p)) return false;
  const wagi = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3];
  const suma = wagi.reduce((s, w, i) => s + w * Number(p[i]), 0);
  return (10 - (suma % 10)) % 10 === Number(p[10]);
}

let licznik = 0;
const noweId = () => `f${Date.now().toString(36)}${(licznik++).toString(36)}`;

export function wykryj(tekst: string): Fragment[] {
  const wyniki: Fragment[] = [];
  for (const r of REGULY) {
    for (const m of tekst.matchAll(r.wzorzec)) {
      const wartosc = r.grupa ? m[r.grupa] : m[0];
      if (!wartosc || (r.sprawdz && !r.sprawdz(wartosc))) continue;
      const start = (m.index ?? 0) + (r.grupa ? m[0].indexOf(wartosc) : 0);
      wyniki.push({ id: noweId(), start, koniec: start + wartosc.length, kategoria: r.kategoria, stan: 'propozycja', zrodlo: 'automat' });
    }
  }
  return scal(wyniki);
}

/** Usuwa nakładające się fragmenty – zostaje dłuższy (np. adres zamiast samego kodu). */
export function scal(fragmenty: Fragment[]): Fragment[] {
  const posortowane = [...fragmenty].sort((a, b) => a.start - b.start || b.koniec - a.koniec);
  const wynik: Fragment[] = [];
  for (const f of posortowane) {
    const ostatni = wynik[wynik.length - 1];
    if (ostatni && f.start < ostatni.koniec) {
      if (f.koniec > ostatni.koniec) {
        // rozszerz poprzedni, zachowując decyzję ręczną, jeśli była
        ostatni.koniec = f.koniec;
      }
      continue;
    }
    wynik.push({ ...f });
  }
  return wynik;
}

export function dodajReczny(fragmenty: Fragment[], start: number, koniec: number): Fragment[] {
  const nowy: Fragment = { id: noweId(), start, koniec, kategoria: 'Zaznaczone ręcznie', stan: 'zaakceptowany', zrodlo: 'reczny' };
  // ręczne zaznaczenie zastępuje automatyczne propozycje, z którymi się pokrywa
  const reszta = fragmenty.filter((f) => f.koniec <= start || f.start >= koniec);
  return [...reszta, nowy].sort((a, b) => a.start - b.start);
}

export const ZNACZNIK = '[dane zanonimizowane]';

/** Tekst wynikowy: zaakceptowane fragmenty zastąpione znacznikiem. */
export function zastosuj(tekst: string, fragmenty: Fragment[]): string {
  const zaakceptowane = fragmenty.filter((f) => f.stan === 'zaakceptowany').sort((a, b) => b.start - a.start);
  let wynik = tekst;
  for (const f of zaakceptowane) wynik = wynik.slice(0, f.start) + ZNACZNIK + wynik.slice(f.koniec);
  return wynik;
}

/**
 * Po edycji tekstu przesuwa fragmenty tak, żeby dalej wskazywały na te same słowa.
 * Fragmenty, których treść zmieniła się w trakcie edycji, są usuwane.
 */
export function przesunPoEdycji(stary: string, nowy: string, fragmenty: Fragment[]): Fragment[] {
  let p = 0;
  while (p < stary.length && p < nowy.length && stary[p] === nowy[p]) p++;
  let ks = stary.length;
  let kn = nowy.length;
  while (ks > p && kn > p && stary[ks - 1] === nowy[kn - 1]) {
    ks--;
    kn--;
  }
  const delta = kn - ks;
  return fragmenty
    .filter((f) => f.koniec <= p || f.start >= ks)
    .map((f) => (f.start >= ks ? { ...f, start: f.start + delta, koniec: f.koniec + delta } : f));
}
