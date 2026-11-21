import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Wniosek } from './types';
import { wnioskiTestowe } from './dane/wnioskiTestowe';
import { dzisIso } from './lib/daty';
import {
  dodajWniosekApi,
  dodajWnioskiWsadowoApi,
  pobierzWnioski,
  usunWniosekApi,
  zastapWnioskiApi,
  zatwierdzOdpowiedzApi,
  zmienWniosekApi,
  type WniosekDoZapisu,
  type WynikZatwierdzenia,
  type ZatwierdzenieOdpowiedziWejscie,
} from './lib/api';

interface Magazyn {
  wnioski: Wniosek[];
  ladowanie: boolean;
  blad: string;
  odswiez: () => Promise<void>;
  dodajWniosek: (w: WniosekDoZapisu) => Promise<Wniosek>;
  dodajWnioskiWsadowo: (lista: WniosekDoZapisu[]) => Promise<Wniosek[]>;
  zmienWniosek: (id: string, w: WniosekDoZapisu) => Promise<Wniosek>;
  zatwierdzOdpowiedz: (id: string, dane: ZatwierdzenieOdpowiedziWejscie) => Promise<WynikZatwierdzenia>;
  usunWniosek: (id: string) => Promise<void>;
  /** podmienia wniosek w stanie po zmianie zapisanej osobnym wywołaniem API (np. odpowiedzi wydziałów) */
  podmienWniosek: (w: Wniosek) => void;
  nastepnyNumer: (rok: string, przesuniecie?: number) => string;
  przywrocDaneTestowe: () => Promise<void>;
}

const KLUCZ_INIT = 'asystent-urzednika.sqlite-zainicjalizowano';

const Kontekst = createContext<Magazyn | null>(null);

export function DostawcaMagazynu({ children }: { children: ReactNode }) {
  const [wnioski, setWnioski] = useState<Wniosek[]>([]);
  const [ladowanie, setLadowanie] = useState(true);
  const [blad, setBlad] = useState('');

  const odswiez = useCallback(async (sygnal?: AbortSignal) => {
    setLadowanie(true);
    setBlad('');
    try {
      let lista = await pobierzWnioski(sygnal);
      let zainicjalizowano = false;
      try {
        zainicjalizowano = localStorage.getItem(KLUCZ_INIT) === '1';
      } catch {
        /* brak dostępu do localStorage */
      }
      if (lista.length === 0 && !zainicjalizowano) {
        lista = await dodajWnioskiWsadowoApi(wnioskiTestowe(dzisIso()));
        try {
          localStorage.setItem(KLUCZ_INIT, '1');
        } catch {
          /* ignorujemy */
        }
      }
      setWnioski(lista);
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setBlad(e instanceof Error ? e.message : String(e));
    } finally {
      setLadowanie(false);
    }
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    void odswiez(ac.signal);
    return () => ac.abort();
  }, [odswiez]);

  const nastepnyNumer = useCallback(
    (rok: string, przesuniecie = 0) => {
      const numery = wnioski
        .map((w) => w.numer.match(/^BKS\.IV\.1431\.(\d+)\.(\d{4})$/))
        .filter((m): m is RegExpMatchArray => !!m && m[2] === rok)
        .map((m) => Number(m[1]));
      return `BKS.IV.1431.${(numery.length ? Math.max(...numery) : 0) + 1 + przesuniecie}.${rok}`;
    },
    [wnioski],
  );

  const dodajWniosek = useCallback(async (w: WniosekDoZapisu) => {
    const zapisany = await dodajWniosekApi(w);
    setWnioski((prev) => [...prev, zapisany]);
    return zapisany;
  }, []);

  const dodajWnioskiWsadowo = useCallback(async (lista: WniosekDoZapisu[]) => {
    const zapisane = await dodajWnioskiWsadowoApi(lista);
    setWnioski((prev) => [...prev, ...zapisane]);
    return zapisane;
  }, []);

  const zmienWniosek = useCallback(async (id: string, w: WniosekDoZapisu) => {
    const zapisany = await zmienWniosekApi(id, w);
    setWnioski((prev) => prev.map((x) => (x.id === id ? zapisany : x)));
    return zapisany;
  }, []);

  const zatwierdzOdpowiedz = useCallback(async (id: string, dane: ZatwierdzenieOdpowiedziWejscie) => {
    const wynik = await zatwierdzOdpowiedzApi(id, dane);
    setWnioski((prev) => prev.map((x) => (x.id === id ? wynik.wniosek : x)));
    return wynik;
  }, []);

  const podmienWniosek = useCallback((w: Wniosek) => {
    setWnioski((prev) => prev.map((x) => (x.id === w.id ? w : x)));
  }, []);

  const usunWniosek = useCallback(async (id: string) => {
    await usunWniosekApi(id);
    setWnioski((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const przywrocDaneTestowe = useCallback(async () => {
    setBlad('');
    const zapisane = await zastapWnioskiApi(wnioskiTestowe(dzisIso()));
    setWnioski(zapisane);
    try {
      localStorage.setItem(KLUCZ_INIT, '1');
    } catch {
      /* ignorujemy */
    }
  }, []);

  const wartosc = useMemo<Magazyn>(
    () => ({
      wnioski,
      ladowanie,
      blad,
      odswiez: () => odswiez(),
      dodajWniosek,
      dodajWnioskiWsadowo,
      zmienWniosek,
      zatwierdzOdpowiedz,
      podmienWniosek,
      usunWniosek,
      nastepnyNumer,
      przywrocDaneTestowe,
    }),
    [wnioski, ladowanie, blad, odswiez, dodajWniosek, dodajWnioskiWsadowo, zmienWniosek, zatwierdzOdpowiedz, podmienWniosek, usunWniosek, nastepnyNumer, przywrocDaneTestowe],
  );

  return <Kontekst.Provider value={wartosc}>{children}</Kontekst.Provider>;
}

export function useMagazyn(): Magazyn {
  const m = useContext(Kontekst);
  if (!m) throw new Error('useMagazyn poza DostawcaMagazynu');
  return m;
}
