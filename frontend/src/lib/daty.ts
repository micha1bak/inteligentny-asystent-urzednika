// Operacje na datach w formacie YYYY-MM-DD, liczone w czasie lokalnym (bez stref).

export function zIso(iso: string): Date {
  const [r, m, d] = iso.split('-').map(Number);
  return new Date(r, m - 1, d);
}

export function doIso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dz = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${dz}`;
}

export function dzisIso(): string {
  return doIso(new Date());
}

export function dodajDni(iso: string, dni: number): string {
  const d = zIso(iso);
  d.setDate(d.getDate() + dni);
  return doIso(d);
}

export function dodajMiesiace(iso: string, mies: number): string {
  const d = zIso(iso);
  const dzien = d.getDate();
  d.setDate(1);
  d.setMonth(d.getMonth() + mies);
  const ostatni = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  d.setDate(Math.min(dzien, ostatni));
  return doIso(d);
}

/** Liczba dni kalendarzowych od `od` do `do` (ujemna, gdy `do` jest wcześniej). */
export function roznicaDni(od: string, do_: string): number {
  const ms = zIso(do_).getTime() - zIso(od).getTime();
  return Math.round(ms / 86_400_000);
}

const fmt = new Intl.DateTimeFormat('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric' });
export function formatuj(iso?: string): string {
  return iso ? fmt.format(zIso(iso)) : '—';
}

const fmtSlownie = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' });
export function formatujSlownie(iso: string): string {
  return fmtSlownie.format(zIso(iso));
}
