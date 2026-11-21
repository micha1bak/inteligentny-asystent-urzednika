// Klient backendu (FastAPI). W trybie deweloperskim Vite przekierowuje /api na http://127.0.0.1:8000.

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

export async function pobierzPropozycje(z: ZapytanieOPropozycje, sygnal?: AbortSignal): Promise<Propozycja> {
  let odp: Response;
  try {
    odp = await fetch('/api/propozycja-odpowiedzi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.fromEntries(Object.entries(z).filter(([, v]) => v))),
      signal: sygnal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new Error('Brak połączenia z backendem. Uruchom go poleceniem: uv run inteligentny-asystent-urzednika');
  }
  if (!odp.ok) {
    const szczegoly = await odp.json().catch(() => null);
    const detail = szczegoly?.detail;
    const komunikat = typeof detail === 'string' ? detail : Array.isArray(detail) ? 'Niepoprawne dane wniosku (za krótka treść?).' : '';
    if (odp.status === 502 && !komunikat) throw new Error('Backend nie działa. Uruchom go poleceniem: uv run inteligentny-asystent-urzednika');
    throw new Error(komunikat || `Błąd backendu (${odp.status}).`);
  }
  return odp.json();
}
