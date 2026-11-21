import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMagazyn } from '../magazyn';
import type { Wniosek } from '../types';
import { dodajDni, doIso, dzisIso, formatuj, zIso } from '../lib/daty';
import { czyDzienWolny, pilnosc, type Pilnosc } from '../lib/terminy';
import { Pozostalo, ZnaczekStatusu } from '../components/Znaczki';
import type { ZWniosku } from './NowaSprawaArchiwum';

type Wiersz = Wniosek & { lp: number; termin: string; pozostalo: number; pilnosc: Pilnosc };

const PILNE: Pilnosc[] = ['po_terminie', 'dzis', 'jutro'];

export default function Kalendarz() {
  const { wnioski, przywrocDaneTestowe } = useMagazyn();
  const dzis = dzisIso();
  const lata = useMemo(
    () => [...new Set([dzis.slice(0, 4), ...wnioski.map((w) => w.dataWplywu.slice(0, 4))])].sort().reverse(),
    [wnioski, dzis],
  );
  const [rok, setRok] = useState(dzis.slice(0, 4));
  const [tylkoPilne, setTylkoPilne] = useState(false);
  const [widok, setWidok] = useState<'tabela' | 'miesiac'>('tabela');

  const wiersze: Wiersz[] = useMemo(
    () =>
      wnioski
        .filter((w) => w.dataWplywu.startsWith(rok))
        .sort((a, b) => a.dataWplywu.localeCompare(b.dataWplywu) || a.numer.localeCompare(b.numer, 'pl', { numeric: true }))
        .map((w, i) => ({ ...w, lp: i + 1, ...pilnosc(w, dzis) })),
    [wnioski, rok, dzis],
  );

  const liczba = (p: Pilnosc) => wiersze.filter((w) => w.pilnosc === p).length;
  const pilnych = wiersze.filter((w) => PILNE.includes(w.pilnosc)).length;
  const widoczne = tylkoPilne ? wiersze.filter((w) => PILNE.includes(w.pilnosc)) : wiersze;

  return (
    <>
      <div className="rzad rozsun">
        <div>
          <h1>Kalendarz wniosków</h1>
          <p className="podtytul">Wnioski od najstarszych. Termin liczony wg art. 13 UDIP z przesunięciem na dzień roboczy (art. 57 § 4 KPA).</p>
        </div>
        <div className="rzad">
          <label style={{ flexDirection: 'row', alignItems: 'center' }}>
            Rok
            <select value={rok} onChange={(e) => setRok(e.target.value)} style={{ width: 90 }}>
              {lata.map((r) => <option key={r}>{r}</option>)}
            </select>
          </label>
          <Link className="przycisk glowny" to="/nowy">+ Dodaj wniosek</Link>
        </div>
      </div>

      <div className="kafle">
        <div className="kafel"><span className={`liczba ${liczba('po_terminie') ? 'pil-po_terminie' : ''}`}>{liczba('po_terminie')}</span><span className="maly">Po terminie</span></div>
        <div className="kafel"><span className={`liczba ${liczba('dzis') ? 'pil-dzis' : ''}`}>{liczba('dzis')}</span><span className="maly">Termin dziś</span></div>
        <div className="kafel"><span className={`liczba ${liczba('jutro') ? 'pil-jutro' : ''}`}>{liczba('jutro')}</span><span className="maly">Termin jutro</span></div>
        <div className="kafel"><span className="liczba">{wiersze.filter((w) => w.pilnosc !== 'zakonczony').length}</span><span className="maly">W toku</span></div>
        <div className="kafel"><span className="liczba">{wiersze.length}</span><span className="maly">Wszystkie w {rok} r.</span></div>
      </div>

      <div className="karta">
        <div className="rzad rozsun" style={{ marginBottom: 12 }}>
          <div className="rzad">
            <div className="zakladki">
              <button className={widok === 'tabela' ? 'aktywna' : ''} onClick={() => setWidok('tabela')}>Tabela</button>
              <button className={widok === 'miesiac' ? 'aktywna' : ''} onClick={() => setWidok('miesiac')}>Kalendarz</button>
            </div>
            <label style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <input type="checkbox" style={{ width: 'auto' }} checked={tylkoPilne} onChange={(e) => setTylkoPilne(e.target.checked)} />
              Tylko pilne ({pilnych})
            </label>
          </div>
          <div className="legenda">
            <span className="l-po">po terminie</span>
            <span className="l-dzis">termin dziś</span>
            <span className="l-jutro">termin jutro</span>
          </div>
        </div>

        {widok === 'tabela' ? <Tabela wiersze={widoczne} /> : <Miesiac wiersze={widoczne} dzis={dzis} rok={rok} />}

        {wiersze.length === 0 && (
          <p className="maly" style={{ marginTop: 16 }}>
            Brak wniosków w {rok} r.{' '}
            <button className="maly-p" onClick={przywrocDaneTestowe}>Wczytaj 10 wniosków testowych</button>
          </p>
        )}
      </div>
      <p className="maly" style={{ marginTop: 12 }}>
        <button className="maly-p" onClick={() => confirm('Usunąć wszystkie zmiany i wczytać od nowa 10 wniosków testowych?') && przywrocDaneTestowe()}>
          Przywróć dane testowe
        </button>
      </p>
    </>
  );
}

function Tabela({ wiersze }: { wiersze: Wiersz[] }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table>
        <thead>
          <tr>
            <th>Lp.</th>
            <th>Nr wniosku</th>
            <th>Data wpływu</th>
            <th>Temat wniosku</th>
            <th>Os.</th>
            <th>Termin</th>
            <th>Pozostało</th>
            <th>Status</th>
            <th>Data odpowiedzi</th>
          </tr>
        </thead>
        <tbody>
          {wiersze.map((w) => (
            <tr key={w.id} className={`p-${w.pilnosc}`}>
              <td>{w.lp}</td>
              <td className="numer nowrap">{w.numer}</td>
              <td className="nowrap">{formatuj(w.dataWplywu)}</td>
              <td>
                <span style={{ fontWeight: 500 }}>{w.temat}</span>
                <div className="maly">{w.wnioskodawca}</div>
              </td>
              <td title="Inicjały osoby prowadzącej">{w.inicjaly}</td>
              <td className="nowrap">{formatuj(w.termin)}</td>
              <td className="nowrap"><Pozostalo pilnosc={w.pilnosc} pozostalo={w.pozostalo} /></td>
              <td>
                <ZnaczekStatusu status={w.status} dniKwerendy={w.dniKwerendy} />
                {w.status === 'odpowiedz_wyslana' && (
                  <div>
                    <Link
                      className="maly"
                      to="/archiwum/nowa"
                      state={{ sygnatura: w.numer, wniosek: w.tresc, dataOdpowiedzi: w.dataOdpowiedzi } satisfies ZWniosku}
                    >
                      Dodaj do archiwum
                    </Link>
                  </div>
                )}
              </td>
              <td className="nowrap">{formatuj(w.dataOdpowiedzi)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {wiersze.length === 0 && <p className="maly">Brak wniosków spełniających kryteria.</p>}
    </div>
  );
}

const DNI = ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Nd'];

function Miesiac({ wiersze, dzis, rok }: { wiersze: Wiersz[]; dzis: string; rok: string }) {
  const [poczatek, setPoczatek] = useState(() => (dzis.startsWith(rok) ? dzis.slice(0, 8) + '01' : `${rok}-01-01`));
  const d0 = zIso(poczatek);
  const nazwa = d0.toLocaleDateString('pl-PL', { month: 'long', year: 'numeric' });
  const pierwszy = dodajDni(poczatek, -((d0.getDay() + 6) % 7));
  const dni = Array.from({ length: 42 }, (_, i) => dodajDni(pierwszy, i));
  const zmien = (o: number) => setPoczatek(doIso(new Date(d0.getFullYear(), d0.getMonth() + o, 1)));
  const wgTerminu = new Map<string, Wiersz[]>();
  for (const w of wiersze) {
    const klucz = w.status === 'odpowiedz_wyslana' && w.dataOdpowiedzi ? w.dataOdpowiedzi : w.termin;
    wgTerminu.set(klucz, [...(wgTerminu.get(klucz) ?? []), w]);
  }

  return (
    <>
      <div className="rzad" style={{ marginBottom: 10 }}>
        <button className="maly-p" onClick={() => zmien(-1)}>‹</button>
        <strong style={{ minWidth: 160, textAlign: 'center', textTransform: 'capitalize' }}>{nazwa}</strong>
        <button className="maly-p" onClick={() => zmien(1)}>›</button>
        <span className="maly">Wnioski pokazane w dniu terminu odpowiedzi.</span>
      </div>
      <div className="miesiac">
        {DNI.map((d) => <div key={d} className="naglowek">{d}</div>)}
        {dni.map((d) => (
          <div
            key={d}
            className={`dzien ${d.slice(0, 7) !== poczatek.slice(0, 7) ? 'inny' : ''} ${czyDzienWolny(d) ? 'wolny' : ''} ${d === dzis ? 'dzisiaj' : ''}`}
          >
            <span className="nr">{Number(d.slice(8))}</span>
            {(wgTerminu.get(d) ?? []).map((w) => (
              <span key={w.id} className={`chip p-${w.pilnosc}`} title={`${w.numer} – ${w.temat}`}>
                {w.inicjaly} · {w.temat}
              </span>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}
