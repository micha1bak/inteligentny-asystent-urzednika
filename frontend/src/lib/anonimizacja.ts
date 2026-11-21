// Anonimizacja tekstu: propozycje (szare) i fragmenty ukryte przez urzędnika (czarne).
// Ukrycie dotyczy każdego wystąpienia danego tekstu.

export interface Ukrycie {
  tekst: string;
  /** rodzaj danych, np. „imię i nazwisko”, „adres”, „zaznaczone” (ręcznie przez urzędnika) */
  rodzaj: string;
  stan: 'proponowane' | 'ukryte';
}

/** Sugestia z backendu (POST /api/anonimizacja/sugestie). */
export interface Sugestia {
  rodzaj: string;
  tekst: string;
  start: number;
  koniec: number;
}

export interface Odcinek {
  tekst: string;
  ukrycie?: Ukrycie;
}

const ZNAK = '█';

/** Dzieli tekst na odcinki zwykłe i odcinki objęte ukryciem (dłuższe frazy mają pierwszeństwo, bez nakładania się). */
export function podzielNaUkrycia(tekst: string, ukrycia: Ukrycie[]): Odcinek[] {
  const trafienia: { start: number; koniec: number; u: Ukrycie }[] = [];
  for (const u of [...ukrycia].filter((x) => x.tekst.trim()).sort((a, b) => b.tekst.length - a.tekst.length)) {
    let od = 0;
    for (;;) {
      const i = tekst.indexOf(u.tekst, od);
      if (i < 0) break;
      const k = i + u.tekst.length;
      if (trafienia.every((t) => k <= t.start || i >= t.koniec)) trafienia.push({ start: i, koniec: k, u });
      od = k;
    }
  }
  trafienia.sort((a, b) => a.start - b.start);
  const wynik: Odcinek[] = [];
  let poz = 0;
  for (const t of trafienia) {
    if (t.start > poz) wynik.push({ tekst: tekst.slice(poz, t.start) });
    wynik.push({ tekst: tekst.slice(t.start, t.koniec), ukrycie: t.u });
    poz = t.koniec;
  }
  if (poz < tekst.length) wynik.push({ tekst: tekst.slice(poz) });
  return wynik;
}

/** Tekst po anonimizacji: ukryte fragmenty zastąpione znakiem █ tej samej długości (propozycje bez zmian). */
export function zastosujUkrycia(tekst: string, ukrycia: Ukrycie[]): string {
  return podzielNaUkrycia(tekst, ukrycia.filter((u) => u.stan === 'ukryte'))
    .map((o) => (o.ukrycie ? ZNAK.repeat(o.tekst.length) : o.tekst))
    .join('');
}

/** Łączy nowe sugestie z dotychczasowymi decyzjami urzędnika (ukryte zostają ukryte, odrzucone nie wracają). */
export function scalSugestie(dotychczasowe: Ukrycie[], sugestie: Sugestia[], odrzucone: string[] = []): Ukrycie[] {
  const wynik = [...dotychczasowe];
  for (const s of sugestie) {
    if (odrzucone.includes(s.tekst) || wynik.some((u) => u.tekst === s.tekst)) continue;
    wynik.push({ tekst: s.tekst, rodzaj: s.rodzaj, stan: 'proponowane' });
  }
  return wynik;
}

/** Kliknięcie fragmentu: propozycja -> ukryte, ukryte -> propozycja. */
export function przelaczUkrycie(ukrycia: Ukrycie[], tekst: string): Ukrycie[] {
  return ukrycia.map((u) => (u.tekst === tekst ? { ...u, stan: u.stan === 'ukryte' ? 'proponowane' : 'ukryte' } : u));
}

/** Ręczne ukrycie zaznaczonego tekstu. */
export function dodajUkrycie(ukrycia: Ukrycie[], tekst: string, rodzaj = 'zaznaczone'): Ukrycie[] {
  const t = tekst.trim();
  if (t.length < 2) return ukrycia;
  const istniejace = ukrycia.find((u) => u.tekst === t);
  if (istniejace) return ukrycia.map((u) => (u.tekst === t ? { ...u, stan: 'ukryte' } : u));
  return [...ukrycia, { tekst: t, rodzaj, stan: 'ukryte' }];
}
