import { useEffect, useState } from 'react';
import { dodajOdpowiedzWydzialuApi, pobierzJednostki, usunOdpowiedzWydzialuApi, type JednostkaUmb } from '../lib/api';
import type { OdpowiedzWydzialu, Wniosek } from '../types';
import StrefaPliku from './StrefaPliku';

/**
 * Odpowiedzi z wydziałów (krok 6 instrukcji UMB): urzędnik wgrywa plik PDF/Word z odpowiedzią komórki merytorycznej
 * (albo wkleja tekst). Treść trafia do sprawy i jest podstawą projektu pisma (krok 7).
 */
export default function OdpowiedziWydzialow({ wniosekId, odpowiedzi, wybranyWydzial = '', onZmiana }: {
  wniosekId: string;
  odpowiedzi: OdpowiedzWydzialu[];
  /** jednostka wybrana wyżej w „Zapytanie do wydziału” dla tego wniosku – ustawiana automatycznie */
  wybranyWydzial?: string;
  onZmiana: (w: Wniosek) => void;
}) {
  const [jednostki, setJednostki] = useState<JednostkaUmb[]>([]);
  const [wydzial, setWydzial] = useState(wybranyWydzial);
  const [wklejony, setWklejony] = useState('');
  const [rozwiniete, setRozwiniete] = useState<string | null>(null);
  const [blad, setBlad] = useState('');
  const [trwa, setTrwa] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    pobierzJednostki(ac.signal).then(setJednostki).catch(() => {});
    return () => ac.abort();
  }, []);

  useEffect(() => {
    if (wybranyWydzial) {
      setWydzial(wybranyWydzial);
      setBlad('');
    }
  }, [wybranyWydzial]);

  async function dodaj(tresc: string, nazwaPliku: string) {
    if (!wydzial) {
      setBlad('Najpierw wybierz wydział, od którego jest odpowiedź.');
      return;
    }
    if (!tresc.trim()) {
      setBlad('Plik nie zawiera tekstu.');
      return;
    }
    setTrwa(true);
    setBlad('');
    try {
      onZmiana(await dodajOdpowiedzWydzialuApi(wniosekId, { wydzial, nazwa_pliku: nazwaPliku, tresc }));
      setWklejony('');
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    } finally {
      setTrwa(false);
    }
  }

  async function usun(o: OdpowiedzWydzialu) {
    if (!confirm(`Usunąć odpowiedź: ${o.wydzial}${o.nazwaPliku ? ` (${o.nazwaPliku})` : ''}?`)) return;
    try {
      onZmiana(await usunOdpowiedzWydzialuApi(wniosekId, o.id));
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="karta">
      <h2>Odpowiedzi z wydziałów ({odpowiedzi.length})</h2>
      <p className="maly" style={{ margin: '0 0 10px' }}>
        Wgraj odpowiedź komórki merytorycznej (PDF lub Word). Projekt pisma zostanie oparty na jej treści.
      </p>
      <label>
        <span>
          Wydział / jednostka
          {wybranyWydzial && wydzial === wybranyWydzial && ' (z zapytania do wydziału)'}
        </span>
        <select value={wydzial} onChange={(e) => setWydzial(e.target.value)}>
          <option value="">— wybierz —</option>
          {wydzial && !jednostki.some((j) => j.nazwa === wydzial) && (
            <option value={wydzial}>{wydzial}</option>
          )}
          {jednostki.map((j) => <option key={j.symbol} value={j.nazwa}>{j.nazwa}</option>)}
        </select>
      </label>
      <div style={{ marginTop: 8, opacity: wydzial ? 1 : 0.55 }}>
        <StrefaPliku
          napis={wydzial ? 'Przeciągnij plik odpowiedzi (PDF/Word) albo kliknij' : 'Najpierw wybierz wydział'}
          onWczytano={(w, plik) => void dodaj(w.odreczny ? '' : w.tekst, plik.name)}
        />
      </div>
      <details style={{ marginTop: 8 }}>
        <summary className="maly">…albo wklej treść odpowiedzi</summary>
        <textarea rows={4} value={wklejony} onChange={(e) => setWklejony(e.target.value)} />
        <button className="maly-p" disabled={trwa || !wklejony.trim()} onClick={() => void dodaj(wklejony, '')}>Dodaj odpowiedź</button>
      </details>
      {trwa && <div className="postep postep-ciagly"><div /></div>}
      {blad && <div className="blad">{blad}</div>}
      {odpowiedzi.length > 0 && (
        <ul className="lista-odpowiedzi">
          {odpowiedzi.map((o) => (
            <li key={o.id}>
              <div className="rzad rozsun">
                <span>
                  <strong>{o.wydzial}</strong>
                  <span className="maly"> {o.nazwaPliku || 'tekst wklejony'} · {new Date(o.dodano).toLocaleDateString('pl-PL')}</span>
                </span>
                <span className="rzad">
                  <button className="maly-p" onClick={() => setRozwiniete(rozwiniete === o.id ? null : o.id)}>
                    {rozwiniete === o.id ? 'Zwiń' : 'Pokaż treść'}
                  </button>
                  <button className="maly-p" style={{ color: 'var(--czerwony)' }} onClick={() => void usun(o)}>Usuń</button>
                </span>
              </div>
              {rozwiniete === o.id && <div className="pole-tekstu" style={{ marginTop: 6 }}>{o.tresc}</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
