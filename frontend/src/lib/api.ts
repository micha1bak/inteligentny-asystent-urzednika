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
    const komunikat = typeof detail === 'string' ? detail : Array.isArray(detail) ? 'Niepoprawne dane wniosku (za krótka treść?).' : '';
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

/** Odczyt pliku wniosku przez backend: filtr pisma odręcznego + konwersja na tekst. */
export async function konwertujPlik(plik: File, sygnal?: AbortSignal): Promise<WynikKonwersji> {
  const dane = new FormData();
  dane.append('plik', plik, plik.name);
  const odp = await wyslij('/api/konwersja', { method: 'POST', body: dane, signal: sygnal });
  return odp.json();
}

export interface FragmentPrzepisu {
  etykieta: string;
  akt: string;
  plik: string;
  strona: number | null;
  tresc: string;
  pelny_artykul: string | null;
  dopasowanie: 'dokladne' | 'artykul' | 'tekstowe';
}

export interface WynikWyszukiwaniaPrzepisow {
  zapytanie: string;
  wyniki: FragmentPrzepisu[];
  dostepne_pliki: string[];
}

export interface DokumentPrawnyInfo {
  plik: string;
  akt: string;
  nazwa: string;
  liczba_jednostek: number;
}

/** Deterministyczne wyszukiwanie przepisu lub frazy w folderze „Dokumenty i podstawy prawne” (bez modelu AI). */
export async function szukajPrzepisow(
  q: string,
  akt?: string,
  limit = 8,
  sygnal?: AbortSignal,
): Promise<WynikWyszukiwaniaPrzepisow> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (akt) params.set('akt', akt);
  const odp = await wyslij(`/api/przepisy/szukaj?${params.toString()}`, { method: 'GET', signal: sygnal });
  return odp.json();
}

/** Lista plików zaindeksowanych w folderze „Dokumenty i podstawy prawne”. */
export async function pobierzDokumentyPrawne(sygnal?: AbortSignal): Promise<DokumentPrawnyInfo[]> {
  const odp = await wyslij('/api/przepisy/dokumenty', { method: 'GET', signal: sygnal });
  return odp.json();
}
