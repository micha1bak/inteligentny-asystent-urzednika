import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { DokumentBazy, SprawaArchiwalna, Wniosek } from './types';
import { wnioskiTestowe } from './dane/wnioskiTestowe';
import { ARCHIWUM_BAZOWE } from './dane/referencje';
import { dzisIso } from './lib/daty';

/**
 * Magazyn danych prototypu: trzymany w przeglądarce (localStorage), bez serwera.
 * Interfejs (lista operacji poniżej) jest tym, co później zastąpi API backendu.
 */
interface Stan {
  wersja: 1;
  wnioski: Wniosek[];
  archiwumDodane: SprawaArchiwalna[];
  dokumenty: DokumentBazy[];
}

interface Magazyn extends Stan {
  archiwum: SprawaArchiwalna[];
  dodajWniosek: (w: Omit<Wniosek, 'id' | 'numer'> & { numer?: string }) => Wniosek;
  aktualizujWniosek: (id: string, zmiany: Partial<Wniosek>) => void;
  usunWniosek: (id: string) => void;
  dodajDoArchiwum: (s: Omit<SprawaArchiwalna, 'id' | 'zrodlo'>) => void;
  dodajDokument: (d: Omit<DokumentBazy, 'id' | 'dodano'>) => void;
  usunDokument: (id: string) => void;
  nastepnyNumer: (rok: string) => string;
  przywrocDaneTestowe: () => void;
}

const KLUCZ = 'asystent-urzednika.v1';

function stanPoczatkowy(): Stan {
  return { wersja: 1, wnioski: wnioskiTestowe(dzisIso()), archiwumDodane: [], dokumenty: [] };
}

function wczytaj(): Stan {
  try {
    const surowe = localStorage.getItem(KLUCZ);
    if (surowe) {
      const s = JSON.parse(surowe) as Stan;
      if (s.wersja === 1 && Array.isArray(s.wnioski)) return s;
    }
  } catch {
    /* brak dostępu do localStorage – działamy w pamięci */
  }
  return stanPoczatkowy();
}

const Kontekst = createContext<Magazyn | null>(null);

const id = () => crypto.randomUUID();

export function DostawcaMagazynu({ children }: { children: ReactNode }) {
  const [stan, ustaw] = useState<Stan>(wczytaj);

  useEffect(() => {
    try {
      localStorage.setItem(KLUCZ, JSON.stringify(stan));
    } catch {
      /* ignorujemy – dane zostają w pamięci karty */
    }
  }, [stan]);

  const nastepnyNumer = useCallback(
    (rok: string) => {
      const numery = stan.wnioski
        .map((w) => w.numer.match(/^BKS\.IV\.1431\.(\d+)\.(\d{4})$/))
        .filter((m): m is RegExpMatchArray => !!m && m[2] === rok)
        .map((m) => Number(m[1]));
      return `BKS.IV.1431.${(numery.length ? Math.max(...numery) : 0) + 1}.${rok}`;
    },
    [stan.wnioski],
  );

  const wartosc = useMemo<Magazyn>(
    () => ({
      ...stan,
      archiwum: [...ARCHIWUM_BAZOWE, ...stan.archiwumDodane],
      dodajWniosek: (w) => {
        const nowy: Wniosek = { ...w, id: id(), numer: w.numer || nastepnyNumer(w.dataWplywu.slice(0, 4)) };
        ustaw((s) => ({ ...s, wnioski: [...s.wnioski, nowy] }));
        return nowy;
      },
      aktualizujWniosek: (wid, zmiany) =>
        ustaw((s) => ({ ...s, wnioski: s.wnioski.map((w) => (w.id === wid ? { ...w, ...zmiany } : w)) })),
      usunWniosek: (wid) => ustaw((s) => ({ ...s, wnioski: s.wnioski.filter((w) => w.id !== wid) })),
      dodajDoArchiwum: (a) =>
        ustaw((s) => ({ ...s, archiwumDodane: [...s.archiwumDodane, { ...a, id: id(), zrodlo: 'dodane' }] })),
      dodajDokument: (d) =>
        ustaw((s) => ({ ...s, dokumenty: [...s.dokumenty, { ...d, id: id(), dodano: dzisIso() }] })),
      usunDokument: (did) => ustaw((s) => ({ ...s, dokumenty: s.dokumenty.filter((d) => d.id !== did) })),
      nastepnyNumer,
      przywrocDaneTestowe: () => ustaw(stanPoczatkowy()),
    }),
    [stan, nastepnyNumer],
  );

  return <Kontekst.Provider value={wartosc}>{children}</Kontekst.Provider>;
}

export function useMagazyn(): Magazyn {
  const m = useContext(Kontekst);
  if (!m) throw new Error('useMagazyn poza DostawcaMagazynu');
  return m;
}
