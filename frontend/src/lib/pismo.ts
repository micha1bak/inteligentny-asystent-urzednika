import type { Ukrycie } from './anonimizacja';

// Struktura pisma BKS zwracana przez backend (wzor/pismo.py: Pismo) i pomocnicze funkcje podglądu A4.

export interface BlokPisma {
  /** zwrot – „Szanowny Panie,”; akapit – tekst justowany; ad – nagłówek „Ad n”; linia – linia bez justowania */
  typ: 'zwrot' | 'akapit' | 'ad' | 'linia';
  tekst: string;
}

export interface StrukturaPisma {
  naglowek: string[];
  data: string;
  znak: string;
  adresat: string[];
  tytul: string[];
  tresc: BlokPisma[];
  zakonczenie: string;
  podpis: string[];
  stopka: string[];
  /** anonimizacja: propozycje (szare) i fragmenty ukryte przez urzędnika (czarne) */
  ukrycia?: Ukrycie[];
}

/** Wersja tekstowa pisma (do schowka) – ta sama kolejność co Pismo.tekst w backendzie. */
export function pismoNaTekst(p: StrukturaPisma): string {
  const linie = [...p.naglowek, p.data, p.znak, ...p.adresat, ...p.tytul, ...p.tresc.map((b) => b.tekst), p.zakonczenie, ...p.podpis];
  return (p.stopka.length ? [...linie, '', ...p.stopka] : linie).join('\n');
}

export interface ElementUkladu {
  /** wysokość całego elementu */
  wysokosc: number;
  /** element (np. „Ad 1”, zwrot) musi stać na tej samej stronie co początek następnego */
  trzymajZNastepnym?: boolean;
  /** słowa akapitu, który wolno dzielić między strony (jak w oryginalnych pismach) */
  slowa?: string[];
}

/** Fragment elementu na stronie; `od`/`do` – zakres słów, gdy akapit podzielono między strony. */
export interface Kawalek {
  i: number;
  od?: number;
  do?: number;
}

/**
 * Rozkłada elementy na strony o wysokości obszaru treści `dostepne`.
 * Akapity ze `slowa` dzielone są po słowach (co najmniej `minDzielenia` wysokości na stronie),
 * `trzymajZNastepnym` nie zostaje sam na dole strony, element wyższy od strony nie jest dzielony.
 * `mierz(slowa)` zwraca wysokość akapitu złożonego z podanych słów.
 */
export function rozlozNaStrony(
  elementy: ElementUkladu[],
  dostepne: number,
  mierz: (slowa: string[]) => number = () => Infinity,
  minDzielenia = 0,
): Kawalek[][] {
  const strony: Kawalek[][] = [[]];
  let zajete = 0;
  const nowaStrona = () => {
    strony.push([]);
    zajete = 0;
  };
  // ile miejsca musi zostać na początek elementu i (cały albo, przy dzieleniu, minDzielenia)
  const poczatek = (i: number) => {
    const e = elementy[i];
    return e.slowa && e.slowa.length > 1 ? Math.min(e.wysokosc, minDzielenia) : e.wysokosc;
  };

  elementy.forEach((e, i) => {
    let start = 0;
    for (;;) {
      const strona = strony[strony.length - 1];
      const reszta = e.slowa && start > 0 ? e.slowa.slice(start) : undefined;
      const h = reszta ? mierz(reszta) : e.wysokosc;
      const potrzeba = h + (e.trzymajZNastepnym && i + 1 < elementy.length ? poczatek(i + 1) : 0);
      const kawalek: Kawalek = start > 0 ? { i, od: start, do: e.slowa!.length } : { i };

      if (zajete + potrzeba <= dostepne || (!strona.length && !e.slowa)) {
        strona.push(kawalek);
        zajete += h;
        return;
      }
      const wolne = dostepne - zajete;
      if (e.slowa && e.slowa.length - start > 1 && wolne >= minDzielenia && wolne > 0) {
        // najwięcej słów, które mieszczą się w wolnym miejscu (wyszukiwanie binarne)
        let lo = 0;
        let hi = e.slowa.length - start - 1;
        while (lo < hi) {
          const k = Math.ceil((lo + hi) / 2);
          if (mierz(e.slowa.slice(start, start + k)) <= wolne) lo = k;
          else hi = k - 1;
        }
        if (lo > 0) {
          strona.push({ i, od: start, do: start + lo });
          start += lo;
          nowaStrona();
          continue;
        }
      }
      if (!strona.length) {
        // nic się nie mieści nawet na pustej stronie – element wychodzi poza stronę
        strona.push(kawalek);
        zajete += h;
        return;
      }
      nowaStrona();
    }
  });
  return strony;
}

/** Dzieli tekst na fragmenty zwykłe i znaczniki [[…]] (do wyróżnienia miejsc do uzupełnienia). */
export function fragmentyZnacznikow(tekst: string): { tekst: string; znacznik: boolean }[] {
  return tekst
    .split(/(\[\[[^\]]*\]\])/)
    .filter(Boolean)
    .map((t) => ({ tekst: t, znacznik: t.startsWith('[[') && t.endsWith(']]') }));
}

export function usunBlok<T>(lista: T[], i: number): T[] {
  return lista.filter((_, j) => j !== i);
}

export function wstawBlok<T>(lista: T[], po: number, blok: T): T[] {
  return [...lista.slice(0, po + 1), blok, ...lista.slice(po + 1)];
}

/**
 * Zakres bloków przesuwanych razem z blokiem `i`: „Ad n” zabiera ze sobą akapity odpowiedzi
 * (do następnego bloku innego typu niż akapit), pozostałe bloki przesuwane są pojedynczo. Zwraca [od, do).
 */
export function zakresBloku(tresc: BlokPisma[], i: number): [number, number] {
  if (tresc[i]?.typ !== 'ad') return [i, i + 1];
  let k = i + 1;
  while (k < tresc.length && tresc[k].typ === 'akapit') k++;
  return [i, k];
}

/** Przenosi bloki [od, do) tak, by stanęły przed blokiem `przed` (0…n). Upuszczenie wewnątrz zakresu nic nie zmienia. */
export function przeniesZakres<T>(lista: T[], od: number, do_: number, przed: number): T[] {
  if (od < 0 || do_ > lista.length || od >= do_ || przed < 0 || przed > lista.length || (przed >= od && przed <= do_)) return lista;
  const zakres = lista.slice(od, do_);
  const reszta = [...lista.slice(0, od), ...lista.slice(do_)];
  const gdzie = przed > od ? przed - zakres.length : przed;
  return [...reszta.slice(0, gdzie), ...zakres, ...reszta.slice(gdzie)];
}

/** ↑ / ↓ dla bloku `i`: „Ad n” przeskakuje całą sąsiednią grupę „Ad”, inne bloki – sąsiedni blok. */
export function przesunBlok(tresc: BlokPisma[], i: number, kierunek: -1 | 1): BlokPisma[] {
  const [od, do_] = zakresBloku(tresc, i);
  if (kierunek < 0) {
    if (od === 0) return tresc;
    let cel = od - 1;
    if (tresc[i].typ === 'ad') {
      // początek poprzedniej grupy „Ad” (albo pojedynczy poprzedni blok)
      while (cel > 0 && tresc[cel].typ === 'akapit' && tresc[cel - 1].typ !== 'zwrot') cel--;
      if (tresc[cel].typ !== 'ad' && cel < od - 1) cel = od - 1;
    }
    return przeniesZakres(tresc, od, do_, cel);
  }
  if (do_ >= tresc.length) return tresc;
  const [, nastepnyKoniec] = tresc[i].typ === 'ad' ? zakresBloku(tresc, do_) : [do_, do_ + 1];
  return przeniesZakres(tresc, od, do_, nastepnyKoniec);
}
