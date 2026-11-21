// Dane referencyjne z katalogu głównego repozytorium (jedno źródło prawdy dla całego zespołu).
import werdykty from '../../../werdykty_wniosek_odpowiedz_dip.json';
import ocena from '../../../ocena_prawna_wniosku_dip_kompletny.json';
import wydzialyJson from './wydzialy.json';
import type { Jednostka, SprawaArchiwalna } from '../types';

export const JEDNOSTKI: Jednostka[] = wydzialyJson.jednostki;

export function jednostka(symbol: string): Jednostka | undefined {
  return JEDNOSTKI.find((j) => j.symbol === symbol);
}

export const SLOWNIK_WERDYKTOW: Record<string, string> = ocena.metadane.slownik_werdyktow;

export const ETAPY_OCENY: { id: string; nazwa: string; informacja: string; zalozenia: string[] }[] =
  ocena.algorytm_oceny_krokowej.map((e) => ({
    id: e.etap_id,
    nazwa: e.nazwa,
    informacja: e.informacja,
    zalozenia: e.zalozenia,
  }));

export const AKTY_PRAWNE: { skrot: string; pelna_nazwa: string; publikator: string }[] =
  ocena.metadane.akty_prawne_i_zrodla;

export const KATALOG_ANONIMIZACJI = ocena.katalog_danych_podlegajacych_anonimizacji;

export const ARCHIWUM_BAZOWE: SprawaArchiwalna[] = werdykty.sprawy.map((s) => ({
  id: `arch-${s.sygnatura}`,
  sygnatura: s.sygnatura,
  data: s.data_odpowiedzi,
  wniosek: s.wniosek_o_co,
  odpowiedz: s.jaka_odpowiedz,
  komorka: s.komorka_merytoryczna,
  werdykt: s.werdykt,
  zrodlo: 'archiwum' as const,
}));
