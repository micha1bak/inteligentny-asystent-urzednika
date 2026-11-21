// Inicjały urzędnika zapamiętane w przeglądarce – używane jako osoba prowadząca wniosek i autor zmian w archiwum.
const KLUCZ = 'asystent.inicjaly';

export function zapamietaneInicjaly(): string {
  try {
    return localStorage.getItem(KLUCZ) ?? '';
  } catch {
    return '';
  }
}

export function zapamietajInicjaly(inicjaly: string): void {
  try {
    localStorage.setItem(KLUCZ, inicjaly);
  } catch {
    /* bez znaczenia */
  }
}
