import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { sprawdzSesjeApi, wylogujApi, zalogujApi, zarejestrujUrzednikaApi } from './lib/api';
import { zapamietajInicjaly } from './lib/inicjaly';

const KLUCZ_TOKENU = 'asystent.sesja.token';

export interface ZalogowanyUrzednik {
  id_u: string;
  inicjaly: string;
}

interface KontekstSesjiWartosc {
  sesja: ZalogowanyUrzednik | null;
  ladowanie: boolean;
  zaloguj: (id_u: string, haslo: string) => Promise<void>;
  zarejestruj: (id_u: string, inicjaly: string, haslo: string) => Promise<void>;
  wyloguj: () => Promise<void>;
}

const KontekstSesji = createContext<KontekstSesjiWartosc | null>(null);

function odczytajToken(): string | null {
  try {
    return sessionStorage.getItem(KLUCZ_TOKENU);
  } catch {
    return null;
  }
}

function zapiszToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(KLUCZ_TOKENU, token);
    else sessionStorage.removeItem(KLUCZ_TOKENU);
  } catch {
    /* brak dostępu do sessionStorage */
  }
}

export function DostawcaSesji({ children }: { children: ReactNode }) {
  const [sesja, setSesja] = useState<ZalogowanyUrzednik | null>(null);
  const [ladowanie, setLadowanie] = useState(true);

  useEffect(() => {
    const ac = new AbortController();
    sprawdzSesjeApi(odczytajToken(), ac.signal)
      .then((stan) => {
        if (stan.zalogowany && stan.id_u) {
          const inicjaly = stan.inicjaly ?? '';
          setSesja({ id_u: stan.id_u, inicjaly });
          if (inicjaly) zapamietajInicjaly(inicjaly);
        } else {
          zapiszToken(null);
          setSesja(null);
        }
      })
      .catch(() => {
        if (!ac.signal.aborted) setSesja(null);
      })
      .finally(() => {
        if (!ac.signal.aborted) setLadowanie(false);
      });
    return () => ac.abort();
  }, []);

  const zaloguj = useCallback(async (id_u: string, haslo: string) => {
    const wynik = await zalogujApi(id_u, haslo);
    zapiszToken(wynik.token);
    if (wynik.inicjaly) zapamietajInicjaly(wynik.inicjaly);
    setSesja({ id_u: wynik.id_u, inicjaly: wynik.inicjaly });
  }, []);

  const zarejestruj = useCallback(async (id_u: string, inicjaly: string, haslo: string) => {
    const wynik = await zarejestrujUrzednikaApi(id_u, inicjaly, haslo);
    zapiszToken(wynik.token);
    if (wynik.inicjaly) zapamietajInicjaly(wynik.inicjaly);
    setSesja({ id_u: wynik.id_u, inicjaly: wynik.inicjaly });
  }, []);

  const wyloguj = useCallback(async () => {
    const token = odczytajToken();
    try {
      await wylogujApi(token);
    } catch {
      /* wyloguj lokalnie nawet jeśli backend jest chwilowo niedostępny */
    }
    zapiszToken(null);
    setSesja(null);
  }, []);

  const wartosc = useMemo<KontekstSesjiWartosc>(
    () => ({ sesja, ladowanie, zaloguj, zarejestruj, wyloguj }),
    [sesja, ladowanie, zaloguj, zarejestruj, wyloguj],
  );

  return <KontekstSesji.Provider value={wartosc}>{children}</KontekstSesji.Provider>;
}

export function useSesja(): KontekstSesjiWartosc {
  const ctx = useContext(KontekstSesji);
  if (!ctx) throw new Error('useSesja poza DostawcaSesji');
  return ctx;
}
