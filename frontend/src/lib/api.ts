// Klient backendu (FastAPI). W trybie deweloperskim Vite przekierowuje /api na http://127.0.0.1:8000.

const BRAK_BACKENDU = 'Brak połączenia z backendem. Uruchom go poleceniem: uv run inteligentny-asystent-urzednika';

export interface ZapytanieOPropozycje {
  tresc: string;
  temat?: string;
  numer?: string;
  data_wplywu?: string;
  wnioskodawca?: string;
}

export interface Propozycja {
  werdykt: string;
  werdykt_opis: string;
  uzasadnienie: string;
  podstawy_prawne: string[];
  komorka_merytoryczna: string;
  podobne_sprawy: { sygnatura: string; dlaczego: string }[];
  dane_do_anonimizacji: string[];
  do_weryfikacji: string[];
  wzor: string;
  wzor_nazwa: string;
  projekt_odpowiedzi: string;
  model: string;
  ostrzezenia: string[];
}

/** Wynik modułu `konwersja` backendu (POST /api/konwersja). */
export interface WynikKonwersji {
  tekst: string;
  /** "tekst" – warstwa tekstowa PDF / DOCX; "model" – co najmniej jedna strona (skan) przepisana przez model */
  zrodlo: 'tekst' | 'model';
  /** dokument zawiera pismo odręczne – tekst nie jest odczytywany, urzędnik ocenia go sam */
  odreczny: boolean;
  strony_odreczne: number[];
  stron: number;
  strony_z_modelu: number[];
  komunikat: string | null;
}

/** Formaty obsługiwane przez moduł `konwersja` (ocr_llm.ROZSZERZENIA). */
export const ROZSZERZENIA_WNIOSKU = ['.pdf', '.docx', '.png', '.jpg', '.jpeg', '.tif', '.tiff'];

async function wyslij(url: string, init: RequestInit): Promise<Response> {
  let odp: Response;
  try {
    odp = await fetch(url, init);
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new Error(BRAK_BACKENDU);
  }
  if (!odp.ok) {
    const szczegoly = await odp.json().catch(() => null);
    const detail = szczegoly?.detail;
    const komunikat = typeof detail === 'string' ? detail : Array.isArray(detail) ? opisBledowWalidacji(detail) : '';
    if (odp.status === 502 && !komunikat) throw new Error(BRAK_BACKENDU);
    throw new Error(komunikat || `Błąd backendu (${odp.status}).`);
  }
  return odp;
}

export async function pobierzPropozycje(z: ZapytanieOPropozycje, sygnal?: AbortSignal): Promise<Propozycja> {
  const odp = await wyslij('/api/propozycja-odpowiedzi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(Object.fromEntries(Object.entries(z).filter(([, v]) => v))),
    signal: sygnal,
  });
  return odp.json();
}

const NAZWY_POL: Record<string, string> = {
  tresc: 'treść wniosku',
  sygnatura: 'sygnatura',
  data_odpowiedzi: 'data odpowiedzi',
  wniosek_o_co: 'czego dotyczył wniosek',
  jaka_odpowiedz: 'jaka była odpowiedź',
  werdykt: 'werdykt',
  autor: 'kto zmienia',
  wniosek: 'treść wniosku',
  odpowiedz: 'treść odpowiedzi',
};

function opisBledowWalidacji(bledy: { loc?: (string | number)[]; type?: string }[]): string {
  const pola = [...new Set(bledy.map((b) => String(b.loc?.at(-1) ?? '')).filter(Boolean))];
  if (!pola.length) return 'Niepoprawne dane.';
  return `Uzupełnij lub popraw: ${pola.map((p) => NAZWY_POL[p] ?? p).join(', ')} (za krótkie albo w złym formacie).`;
}

/** Odczyt pliku wniosku przez backend: filtr pisma odręcznego + konwersja na tekst. */
export async function konwertujPlik(plik: File, sygnal?: AbortSignal): Promise<WynikKonwersji> {
  const dane = new FormData();
  dane.append('plik', plik, plik.name);
  const odp = await wyslij('/api/konwersja', { method: 'POST', body: dane, signal: sygnal });
  return odp.json();
}

// ---------------------------------------------------------------- archiwum spraw

export interface Sprawa {
  sygnatura: string;
  data_odpowiedzi: string;
  komorka_merytoryczna: string;
  wniosek_o_co: string;
  jaka_odpowiedz: string;
  werdykt: string;
  forma_zalatwienia: string;
  etap_i_podstawa: string;
  nieaktualna?: boolean;
}

export interface WpisHistorii {
  kiedy: string;
  kto: string;
  zmiana: string;
  pola: Record<string, { przed: unknown; po: unknown }>;
}

export interface SprawaZArchiwum extends Sprawa {
  historia: WpisHistorii[];
}

export interface Archiwum {
  sprawy: SprawaZArchiwum[];
  /** słownik werdyktów: kod → opis */
  werdykty: Record<string, string>;
  jednostki: string[];
}

export interface PropozycjaWpisu {
  sprawa: Sprawa;
  ostrzezenia: string[];
  model: string;
}

export const PUSTA_SPRAWA: Sprawa = {
  sygnatura: '',
  data_odpowiedzi: '',
  komorka_merytoryczna: '',
  wniosek_o_co: '',
  jaka_odpowiedz: '',
  werdykt: '',
  forma_zalatwienia: '',
  etap_i_podstawa: '',
};

const JSON_NAGLOWKI = { 'Content-Type': 'application/json' };

export async function pobierzArchiwum(sygnal?: AbortSignal): Promise<Archiwum> {
  return (await wyslij('/api/archiwum', { signal: sygnal })).json();
}

export async function dodajDoArchiwum(sprawa: Sprawa, autor: string): Promise<SprawaZArchiwum> {
  const odp = await wyslij('/api/archiwum', { method: 'POST', headers: JSON_NAGLOWKI, body: JSON.stringify({ sprawa, autor }) });
  return odp.json();
}

export async function zmienWArchiwum(sprawa: Sprawa, autor: string): Promise<SprawaZArchiwum> {
  const odp = await wyslij(`/api/archiwum/${encodeURIComponent(sprawa.sygnatura)}`, {
    method: 'PUT',
    headers: JSON_NAGLOWKI,
    body: JSON.stringify({ sprawa, autor }),
  });
  return odp.json();
}

export async function usunZArchiwum(sygnatura: string): Promise<void> {
  await wyslij(`/api/archiwum/${encodeURIComponent(sygnatura)}`, { method: 'DELETE' });
}

/** Model proponuje (zanonimizowany) wpis archiwalny na podstawie treści wniosku i wysłanej odpowiedzi. */
export async function zaproponujWpis(
  z: { wniosek: string; odpowiedz: string; sygnatura?: string },
  sygnal?: AbortSignal,
): Promise<PropozycjaWpisu> {
  const odp = await wyslij('/api/archiwum/propozycja', { method: 'POST', headers: JSON_NAGLOWKI, body: JSON.stringify(z), signal: sygnal });
  return odp.json();
}
