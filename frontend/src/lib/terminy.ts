import type { Wniosek } from '../types';
import { dodajDni, dodajMiesiace, doIso, roznicaDni, zIso } from './daty';

/**
 * Terminy wg UDIP i KPA:
 * - art. 13 ust. 1 UDIP: bez zbędnej zwłoki, nie później niż 14 dni od dnia złożenia wniosku,
 * - art. 13 ust. 2 UDIP: po powiadomieniu wnioskodawcy termin można przedłużyć, maks. do 2 miesięcy,
 * - art. 57 § 1 i § 4 KPA: dnia wpływu nie wlicza się; gdy koniec terminu przypada w sobotę
 *   lub dzień ustawowo wolny, termin upływa w najbliższy dzień roboczy.
 */
export const TERMIN_PODSTAWOWY_DNI = 14;
export const MAKS_PRZEDLUZENIE_MIESIECY = 2;

function wielkanoc(rok: number): Date {
  // algorytm Meeusa/Jonesa/Butchera
  const a = rok % 19;
  const b = Math.floor(rok / 100);
  const c = rok % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const miesiac = Math.floor((h + l - 7 * m + 114) / 31);
  const dzien = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(rok, miesiac - 1, dzien);
}

const cache = new Map<number, Set<string>>();

/** Dni ustawowo wolne od pracy w Polsce (ustawa z 18 stycznia 1951 r.). */
export function dniWolne(rok: number): Set<string> {
  const z = cache.get(rok);
  if (z) return z;
  const w = doIso(wielkanoc(rok));
  const stale = ['01-01', '01-06', '05-01', '05-03', '08-15', '11-01', '11-11', '12-25', '12-26'];
  if (rok >= 2025) stale.push('12-24');
  const zbior = new Set<string>([
    ...stale.map((md) => `${rok}-${md}`),
    w,
    dodajDni(w, 1), // poniedziałek wielkanocny
    dodajDni(w, 49), // Zielone Świątki (niedziela)
    dodajDni(w, 60), // Boże Ciało
  ]);
  cache.set(rok, zbior);
  return zbior;
}

export function czyDzienWolny(iso: string): boolean {
  const d = zIso(iso);
  const dt = d.getDay();
  return dt === 0 || dt === 6 || dniWolne(d.getFullYear()).has(iso);
}

export function najblizszyRoboczy(iso: string): string {
  let d = iso;
  while (czyDzienWolny(d)) d = dodajDni(d, 1);
  return d;
}

export function terminOdpowiedzi(w: Pick<Wniosek, 'dataWplywu' | 'dniKwerendy'>): string {
  const podstawowy = dodajDni(w.dataWplywu, TERMIN_PODSTAWOWY_DNI);
  if (!w.dniKwerendy || w.dniKwerendy <= 0) return najblizszyRoboczy(podstawowy);
  const przedluzony = dodajDni(podstawowy, w.dniKwerendy);
  const maks = dodajMiesiace(w.dataWplywu, MAKS_PRZEDLUZENIE_MIESIECY);
  return najblizszyRoboczy(przedluzony > maks ? maks : przedluzony);
}

/** Ile dni kwerendy można jeszcze dodać, żeby nie przekroczyć 2 miesięcy od wpływu. */
export function maksDniKwerendy(dataWplywu: string): number {
  return roznicaDni(dodajDni(dataWplywu, TERMIN_PODSTAWOWY_DNI), dodajMiesiace(dataWplywu, MAKS_PRZEDLUZENIE_MIESIECY));
}

export type Pilnosc = 'po_terminie' | 'dzis' | 'jutro' | 'wkrotce' | 'w_terminie' | 'zakonczony';

export function pilnosc(w: Wniosek, dzis: string): { pilnosc: Pilnosc; pozostalo: number; termin: string } {
  const termin = terminOdpowiedzi(w);
  const pozostalo = roznicaDni(dzis, termin);
  if (w.status === 'odpowiedz_wyslana') return { pilnosc: 'zakonczony', pozostalo, termin };
  if (pozostalo < 0) return { pilnosc: 'po_terminie', pozostalo, termin };
  if (pozostalo === 0) return { pilnosc: 'dzis', pozostalo, termin };
  // „jutro” = termin w najbliższym dniu roboczym: w piątek i w weekend także termin poniedziałkowy
  if (pozostalo === 1 || termin === najblizszyRoboczy(dodajDni(dzis, 1))) return { pilnosc: 'jutro', pozostalo, termin };
  if (pozostalo <= 3) return { pilnosc: 'wkrotce', pozostalo, termin };
  return { pilnosc: 'w_terminie', pozostalo, termin };
}

export const OPIS_PILNOSCI: Record<Pilnosc, string> = {
  po_terminie: 'Po terminie',
  dzis: 'Termin dziś',
  jutro: 'Termin w następny dzień roboczy',
  wkrotce: 'Do 3 dni',
  w_terminie: 'W terminie',
  zakonczony: 'Zakończony',
};

export function opisPozostalo(pozostalo: number): string {
  if (pozostalo === 0) return 'dziś';
  if (pozostalo === 1) return 'jutro';
  if (pozostalo === -1) return '1 dzień po terminie';
  if (pozostalo < 0) return `${-pozostalo} dni po terminie`;
  return `${pozostalo} dni`;
}

/**
 * Kolejność listy wniosków: według daty wpływu rosnąco (najstarsze na górze);
 * przy tej samej dacie – numer.
 */
export function porownajWgDatyWplywu(
  a: { dataWplywu: string; numer: string },
  b: { dataWplywu: string; numer: string },
): number {
  return (
    a.dataWplywu.localeCompare(b.dataWplywu) ||
    a.numer.localeCompare(b.numer, 'pl', { numeric: true })
  );
}
