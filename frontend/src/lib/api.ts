import type { Status, Wniosek } from '../types';
import type { StrukturaPisma } from './pismo';

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
  pola_wzoru: Record<string, string | string[]>;
  projekt_odpowiedzi: string;
  /** struktura pisma do podglądu w układzie strony A4 (null, gdy backend jej nie zwrócił) */
  pismo: StrukturaPisma | null;
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
  numer: 'numer wniosku',
  data_wplywu: 'data wpływu',
  temat: 'temat',
  dni_kwerendy: 'dni kwerendy',
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

// ---------------------------------------------------------------- przepisy prawne

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

// ---------------------------------------------------------------- baza wniosków (SQLite)

interface WniosekApi {
  id: string;
  numer: string;
  data_wplywu: string;
  temat: string;
  wnioskodawca: string;
  kontakt?: string | null;
  inicjaly: string;
  tresc: string;
  status: Status;
  dni_kwerendy?: number | null;
  data_odpowiedzi?: string | null;
  nazwa_pliku?: string | null;
}

export type WniosekDoZapisu = Omit<Wniosek, 'id' | 'numer'> & { id?: string; numer?: string };

function zApi(w: WniosekApi): Wniosek {
  return {
    id: w.id,
    numer: w.numer,
    dataWplywu: w.data_wplywu,
    temat: w.temat,
    wnioskodawca: w.wnioskodawca,
    kontakt: w.kontakt ?? undefined,
    inicjaly: w.inicjaly,
    tresc: w.tresc,
    status: w.status,
    dniKwerendy: w.dni_kwerendy ?? undefined,
    dataOdpowiedzi: w.data_odpowiedzi ?? undefined,
    nazwaPliku: w.nazwa_pliku ?? undefined,
  };
}

function doApi(w: WniosekDoZapisu) {
  return {
    id: w.id || undefined,
    numer: w.numer || undefined,
    data_wplywu: w.dataWplywu,
    temat: w.temat,
    wnioskodawca: w.wnioskodawca,
    kontakt: w.kontakt || null,
    inicjaly: w.inicjaly,
    tresc: w.tresc,
    status: w.status,
    dni_kwerendy: w.dniKwerendy ?? null,
    data_odpowiedzi: w.dataOdpowiedzi || null,
    nazwa_pliku: w.nazwaPliku || null,
  };
}

export async function pobierzWnioski(sygnal?: AbortSignal): Promise<Wniosek[]> {
  const dane = (await (await wyslij('/api/wnioski', { signal: sygnal })).json()) as WniosekApi[];
  return dane.map(zApi);
}

export async function pobierzWniosek(id: string, sygnal?: AbortSignal): Promise<Wniosek> {
  const dane = (await (await wyslij(`/api/wnioski/${encodeURIComponent(id)}`, { signal: sygnal })).json()) as WniosekApi;
  return zApi(dane);
}

export async function dodajWniosekApi(w: WniosekDoZapisu): Promise<Wniosek> {
  const odp = await wyslij('/api/wnioski', { method: 'POST', headers: JSON_NAGLOWKI, body: JSON.stringify(doApi(w)) });
  return zApi((await odp.json()) as WniosekApi);
}

export async function dodajWnioskiWsadowoApi(lista: WniosekDoZapisu[]): Promise<Wniosek[]> {
  const odp = await wyslij('/api/wnioski/wsadowo', {
    method: 'POST',
    headers: JSON_NAGLOWKI,
    body: JSON.stringify({ wnioski: lista.map(doApi) }),
  });
  return ((await odp.json()) as WniosekApi[]).map(zApi);
}

export async function zastapWnioskiApi(lista: WniosekDoZapisu[]): Promise<Wniosek[]> {
  const odp = await wyslij('/api/wnioski/zastap', {
    method: 'POST',
    headers: JSON_NAGLOWKI,
    body: JSON.stringify({ wnioski: lista.map(doApi) }),
  });
  return ((await odp.json()) as WniosekApi[]).map(zApi);
}

export async function zmienWniosekApi(id: string, w: WniosekDoZapisu): Promise<Wniosek> {
  const odp = await wyslij(`/api/wnioski/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: JSON_NAGLOWKI,
    body: JSON.stringify(doApi(w)),
  });
  return zApi((await odp.json()) as WniosekApi);
}

export async function usunWniosekApi(id: string): Promise<void> {
  await wyslij(`/api/wnioski/${encodeURIComponent(id)}`, { method: 'DELETE' });
}
