import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMagazyn } from '../magazyn';
import { useSesja } from '../sesja';
import type { Wniosek } from '../types';
import { dodajDni, doIso, dzisIso, formatuj, zIso } from '../lib/daty';
import { czyDzienWolny, pilnosc, type Pilnosc, porownajWgDatyWplywu } from '../lib/terminy';
import { Pozostalo, ZnaczekStatusu } from '../components/Znaczki';
import type { ZWniosku } from './NowaSprawaArchiwum';

type Wiersz = Wniosek & { lp: number; termin: string; pozostalo: number; pilnosc: Pilnosc };

const PILNE: Pilnosc[] = ['po_terminie', 'dzis', 'jutro'];

export default function Wnioski() {
  const { wnioski, ladowanie, blad, odswiez, przywrocDaneTestowe } = useMagazyn();
  const { sesja } = useSesja();
  const dzis = dzisIso();
  const lata = useMemo(
    () => [...new Set([dzis.slice(0, 4), ...wnioski.map((w) => w.dataWplywu.slice(0, 4))])].sort().reverse(),
    [wnioski, dzis],
  );
  const [rok, setRok] = useState(dzis.slice(0, 4));
  const [fraza, setFraza] = useState('');
  const [tylkoPilne, setTylkoPilne] = useState(false);
  const [tylkoMoje, setTylkoMoje] = useState(false);
  // wnioski z odpowiedzią odesłaną do wnioskodawcy – wybór zapamiętany w przeglądarce
  const [pokazWyslane, setPokazWyslane] = useState(() => {
    try {
      return localStorage.getItem('pokazWyslane') !== '0';
    } catch {
      return true;
    }
  });
  function przelaczWyslane() {
    setPokazWyslane((p) => {
      try {
        localStorage.setItem('pokazWyslane', p ? '0' : '1');
      } catch {
        /* brak dostępu do pamięci przeglądarki – wybór tylko do odświeżenia strony */
      }
      return !p;
    });
  }
  const [widok, setWidok] = useState<'tabela' | 'miesiac'>('tabela');
  const [trwaReset, setTrwaReset] = useState(false);
  const [bladAkcji, setBladAkcji] = useState('');

  const wiersze: Wiersz[] = useMemo(
    () =>
      wnioski
        .filter((w) => w.dataWplywu.startsWith(rok))
        .map((w) => ({ ...w, ...pilnosc(w, dzis) }))
        .sort(porownajWgDatyWplywu)
        .map((w, i) => ({ ...w, lp: i + 1 })),
    [wnioski, rok, dzis],
  );

  const liczba = (p: Pilnosc) => wiersze.filter((w) => w.pilnosc === p).length;
  const pilnych = wiersze.filter((w) => PILNE.includes(w.pilnosc)).length;
  const mojeId = sesja?.inicjaly.trim().toUpperCase() ?? '';
  const moich = mojeId ? wiersze.filter((w) => w.inicjaly.trim().toUpperCase() === mojeId).length : 0;
  const widoczne = useMemo(() => {
    const f = fraza.trim().toLowerCase();
    return wiersze.filter((w) => {
      if (tylkoPilne && !PILNE.includes(w.pilnosc)) return false;
      if (tylkoMoje && mojeId && w.inicjaly.trim().toUpperCase() !== mojeId) return false;
      if (!pokazWyslane && w.status === 'odpowiedz_wyslana') return false;
      if (!f) return true;
      return [w.numer, w.temat, w.wnioskodawca, w.inicjaly].some((t) => t.toLowerCase().includes(f));
    });
  }, [wiersze, tylkoPilne, tylkoMoje, mojeId, pokazWyslane, fraza]);

  async function resetujDane(potwierdz: boolean) {
    if (potwierdz && !confirm('Usunąć obecne wnioski i wczytać dane testowe?')) return;
    setTrwaReset(true);
    setBladAkcji('');
    try {
      await przywrocDaneTestowe();
    } catch (e) {
      setBladAkcji(e instanceof Error ? e.message : String(e));
    } finally {
      setTrwaReset(false);
    }
  }

  return (
    <>
      <div className="rzad rozsun" style={{ marginBottom: 18 }}>
        <h1>Wnioski</h1>
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

      {(blad || bladAkcji) && (
        <div className="blad rzad rozsun" style={{ marginBottom: 14 }}>
          <span>{blad || bladAkcji}</span>
          {blad && <button className="maly-p" onClick={() => void odswiez()}>Spróbuj ponownie</button>}
        </div>
      )}

      <div className="kafle">
        <div className="kafel"><span className={`liczba ${liczba('po_terminie') ? 'pil-po_terminie' : ''}`}>{liczba('po_terminie')}</span><span className="maly">Po terminie</span></div>
        <div className="kafel"><span className={`liczba ${liczba('dzis') ? 'pil-dzis' : ''}`}>{liczba('dzis')}</span><span className="maly">Termin dziś</span></div>
        <div className="kafel"><span className={`liczba ${liczba('jutro') ? 'pil-jutro' : ''}`}>{liczba('jutro')}</span><span className="maly">Termin w następny dzień roboczy</span></div>
        <div className="kafel"><span className="liczba">{wiersze.filter((w) => w.pilnosc !== 'zakonczony').length}</span><span className="maly">W toku</span></div>
        <div className="kafel"><span className="liczba">{wiersze.length}</span><span className="maly">Wszystkie w {rok} r.</span></div>
      </div>

      <div className="karta">
        <div className="rzad rozsun" style={{ marginBottom: 12 }}>
          <div className="rzad" style={{ flex: 1 }}>
            <div className="zakladki">
              <button className={widok === 'tabela' ? 'aktywna' : ''} onClick={() => setWidok('tabela')}>Tabela</button>
              <button className={widok === 'miesiac' ? 'aktywna' : ''} onClick={() => setWidok('miesiac')}>Kalendarz</button>
            </div>
            <input
              type="search"
              placeholder="Szukaj: nr, temat, wnioskodawca…"
              value={fraza}
              onChange={(e) => setFraza(e.target.value)}
              style={{ maxWidth: 280 }}
            />
            <label style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <input type="checkbox" style={{ width: 'auto' }} checked={tylkoPilne} onChange={(e) => setTylkoPilne(e.target.checked)} />
              Tylko pilne ({pilnych})
            </label>
            {mojeId && (
              <label style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <input type="checkbox" style={{ width: 'auto' }} checked={tylkoMoje} onChange={(e) => setTylkoMoje(e.target.checked)} />
                Tylko moje ({mojeId}: {moich})
              </label>
            )}
            <button className="maly-p" onClick={przelaczWyslane} aria-pressed={!pokazWyslane}
              title="Wnioski, na które odpowiedź została już wysłana do wnioskodawcy">
              {pokazWyslane ? 'Ukryj' : 'Pokaż'} odesłane do wnioskodawcy ({wiersze.filter((w) => w.status === 'odpowiedz_wyslana').length})
            </button>
          </div>
          <div className="legenda">
            <span className="l-po">po terminie</span>
            <span className="l-dzis">termin dziś</span>
            <span className="l-jutro">termin w następny dzień roboczy</span>
          </div>
        </div>

        {ladowanie ? (
          <p className="maly">Wczytuję wnioski…</p>
        ) : widok === 'tabela' ? (
          <Tabela wiersze={widoczne} mojeId={mojeId} />
        ) : (
          <Miesiac wiersze={widoczne} dzis={dzis} rok={rok} />
        )}

        {!ladowanie && wiersze.length === 0 && (
          <p className="maly" style={{ marginTop: 16 }}>
            Brak wniosków w {rok} r.{' '}
            <button className="maly-p" disabled={trwaReset} onClick={() => void resetujDane(false)}>
              Wczytaj dane testowe
            </button>
          </p>
        )}
      </div>

      <p className="maly" style={{ marginTop: 12 }}>
        <button className="maly-p" disabled={trwaReset} onClick={() => void resetujDane(true)}>
          Przywróć dane testowe
        </button>
      </p>
    </>
  );
}

function Tabela({ wiersze, mojeId }: { wiersze: Wiersz[]; mojeId: string }) {
  const nav = useNavigate();

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
            <tr
              key={w.id}
              className={`p-${w.pilnosc} klikalny`}
              tabIndex={0}
              onClick={() => nav(`/wnioski/${encodeURIComponent(w.id)}`)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  nav(`/wnioski/${encodeURIComponent(w.id)}`);
                }
              }}
            >
              <td>{w.lp}</td>
              <td className="numer nowrap">{w.numer}</td>
              <td className="nowrap">{formatuj(w.dataWplywu)}</td>
              <td>
                <span style={{ fontWeight: 500 }}>{w.temat}</span>
                {w.wnioskodawca && <div className="maly">{w.wnioskodawca}</div>}
              </td>
              <td title="Inicjały osoby prowadzącej">
                {mojeId && w.inicjaly.trim().toUpperCase() === mojeId ? (
                  <span className="os-moje">{w.inicjaly}</span>
                ) : (
                  w.inicjaly
                )}
              </td>
              <td className="nowrap">{formatuj(w.termin)}</td>
              <td className="nowrap"><Pozostalo pilnosc={w.pilnosc} pozostalo={w.pozostalo} /></td>
              <td>
                <ZnaczekStatusu status={w.status} dniKwerendy={w.dniKwerendy} />
                {w.status === 'odpowiedz_wyslana' && (
                  <div>
                    <Link
                      className="maly"
                      to="/archiwum/nowa"
                      onClick={(e) => e.stopPropagation()}
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
              <Link
                key={w.id}
                to={`/wnioski/${encodeURIComponent(w.id)}`}
                className={`chip p-${w.pilnosc}`}
                title={`${w.numer} – ${w.temat}`}
              >
                {w.inicjaly} · {w.temat}
              </Link>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}
