import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Wniosek } from './types';
import { wnioskiTestowe } from './dane/wnioskiTestowe';
import { dzisIso } from './lib/daty';

/**
 * Magazyn danych prototypu: trzymany w przeglądarce (localStorage), bez serwera.
 * Interfejs (lista operacji poniżej) jest tym, co później zastąpi API backendu.
 */
interface Stan {
  wersja: 2;
  wnioski: Wniosek[];
}

interface Magazyn extends Stan {
  dodajWniosek: (w: Omit<Wniosek, 'id' | 'numer'> & { numer?: string }) => Wniosek;
  nastepnyNumer: (rok: string) => string;
  przywrocDaneTestowe: () => void;
}

const KLUCZ = 'asystent-urzednika.v2';

function stanPoczatkowy(): Stan {
  return { wersja: 2, wnioski: wnioskiTestowe(dzisIso()) };
}

function wczytaj(): Stan {
  try {
    const surowe = localStorage.getItem(KLUCZ);
    if (surowe) {
      const s = JSON.parse(surowe) as Stan;
      if (s.wersja === 2 && Array.isArray(s.wnioski)) return s;
    }
  } catch {
    /* brak dostępu do localStorage – działamy w pamięci */
  }
  return stanPoczatkowy();
}

const Kontekst = createContext<Magazyn | null>(null);

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
      dodajWniosek: (w) => {
        const nowy: Wniosek = { ...w, id: crypto.randomUUID(), numer: w.numer || nastepnyNumer(w.dataWplywu.slice(0, 4)) };
        ustaw((s) => ({ ...s, wnioski: [...s.wnioski, nowy] }));
        return nowy;
      },
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
