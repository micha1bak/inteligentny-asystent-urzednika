import { useState } from 'react';
import { useMagazyn } from '../magazyn';
import StrefaPliku from '../components/StrefaPliku';
import { AKTY_PRAWNE, JEDNOSTKI, KATALOG_ANONIMIZACJI } from '../dane/referencje';
import { dzisIso, formatuj } from '../lib/daty';
import type { DokumentBazy } from '../types';

export default function BazaWiedzy() {
  const { archiwum, dokumenty, dodajDokument, usunDokument, dodajDoArchiwum } = useMagazyn();
  const [rodzaj, setRodzaj] = useState<DokumentBazy['rodzaj']>('ustawa');
  const [nowa, setNowa] = useState({ sygnatura: '', data: dzisIso(), wniosek: '', odpowiedz: '', komorka: '' });

  return (
    <>
      <h1>Baza wiedzy</h1>
      <p className="podtytul">Ustawy, zarządzenia i archiwalne odpowiedzi, z których korzysta asystent przy wyszukiwaniu podobnych spraw i podpowiadaniu wydziałów.</p>
      <div className="siatka-2">
        <div className="stos">
          <div className="karta">
            <h2>Archiwum odpowiedzi ({archiwum.length})</h2>
            <table>
              <thead><tr><th>Sygnatura</th><th>Data</th><th>Czego dotyczył wniosek</th><th>Komórka</th></tr></thead>
              <tbody>
                {archiwum.map((a) => (
                  <tr key={a.id} style={{ cursor: 'default' }}>
                    <td className="numer nowrap">{a.sygnatura}</td>
                    <td className="nowrap">{formatuj(a.data)}</td>
                    <td>{a.wniosek}<details><summary className="maly">Odpowiedź</summary><span style={{ fontSize: '0.88rem' }}>{a.odpowiedz}</span></details></td>
                    <td className="maly">{a.komorka}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="karta">
            <h2>Dodaj sprawę do archiwum</h2>
            <div className="formularz">
              <label>Sygnatura<input value={nowa.sygnatura} onChange={(e) => setNowa({ ...nowa, sygnatura: e.target.value })} placeholder="BKS.IV.1431.…" /></label>
              <label>Data odpowiedzi<input type="date" value={nowa.data} onChange={(e) => setNowa({ ...nowa, data: e.target.value })} /></label>
              <label className="pelny">
                Komórka merytoryczna
                <select value={nowa.komorka} onChange={(e) => setNowa({ ...nowa, komorka: e.target.value })}>
                  <option value="">—</option>
                  {JEDNOSTKI.map((j) => <option key={j.symbol} value={j.nazwa}>{j.nazwa}</option>)}
                </select>
              </label>
              <div className="pelny"><StrefaPliku napis="Wgraj wniosek archiwalny" onWczytano={(t) => setNowa((n) => ({ ...n, wniosek: t }))} /></div>
              <label className="pelny">Treść wniosku<textarea rows={4} value={nowa.wniosek} onChange={(e) => setNowa({ ...nowa, wniosek: e.target.value })} /></label>
              <div className="pelny"><StrefaPliku napis="Wgraj odpowiedź archiwalną" onWczytano={(t) => setNowa((n) => ({ ...n, odpowiedz: t }))} /></div>
              <label className="pelny">Treść odpowiedzi<textarea rows={4} value={nowa.odpowiedz} onChange={(e) => setNowa({ ...nowa, odpowiedz: e.target.value })} /></label>
            </div>
            <button
              className="glowny"
              style={{ marginTop: 12 }}
              disabled={!nowa.sygnatura || !nowa.wniosek}
              onClick={() => {
                dodajDoArchiwum(nowa);
                setNowa({ sygnatura: '', data: dzisIso(), wniosek: '', odpowiedz: '', komorka: '' });
              }}
            >
              Dodaj do archiwum
            </button>
          </div>
        </div>

        <div className="stos">
          <div className="karta">
            <h2>Akty prawne i zarządzenia</h2>
            <ul className="lista">
              {AKTY_PRAWNE.map((a) => (
                <li key={a.skrot}>
                  <strong>{a.skrot.replaceAll('_', ' ')}</strong>
                  <div style={{ fontSize: '0.9rem' }}>{a.pelna_nazwa}</div>
                  <div className="maly">{a.publikator}</div>
                </li>
              ))}
              {dokumenty.map((d) => (
                <li key={d.id}>
                  <div className="rzad rozsun">
                    <strong>{d.nazwa}</strong>
                    <button className="maly-p" onClick={() => usunDokument(d.id)}>Usuń</button>
                  </div>
                  <div className="maly">{d.rodzaj} · wgrano {formatuj(d.dodano)} · {d.znaki.toLocaleString('pl-PL')} znaków</div>
                </li>
              ))}
            </ul>
            <div className="rzad" style={{ margin: '14px 0 8px' }}>
              <label style={{ flexDirection: 'row', alignItems: 'center' }}>
                Rodzaj
                <select value={rodzaj} onChange={(e) => setRodzaj(e.target.value as DokumentBazy['rodzaj'])} style={{ width: 160 }}>
                  <option value="ustawa">ustawa</option>
                  <option value="zarzadzenie">zarządzenie</option>
                  <option value="inne">inne</option>
                </select>
              </label>
            </div>
            <StrefaPliku
              napis="Wgraj ustawę, nowelizację lub zarządzenie"
              wielokrotny
              onWczytano={(tresc, plik) => dodajDokument({ nazwa: plik.name, rodzaj, znaki: tresc.length, tresc })}
            />
            <p className="maly">Nowe wersje aktów są przechowywane lokalnie. Indeksowanie pełnych tekstów do odpowiedzi modelu – po stronie serwera (etap backendu).</p>
          </div>
          <div className="karta">
            <h2>Katalog anonimizacji</h2>
            <p className="maly">{KATALOG_ANONIMIZACJI.zasada_ogolna}</p>
            <details>
              <summary>{KATALOG_ANONIMIZACJI.pozycje.length} kategorii danych</summary>
              <ol style={{ fontSize: '0.86rem', paddingLeft: 20 }}>
                {KATALOG_ANONIMIZACJI.pozycje.map((p) => (
                  <li key={p.id} title={`${p.podstawa_prawna}\n${p.zalozenia}`}>{p.informacja}</li>
                ))}
              </ol>
            </details>
          </div>
        </div>
      </div>
    </>
  );
}
