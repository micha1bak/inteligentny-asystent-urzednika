import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMagazyn } from '../magazyn';
import { STATUSY, type Status, type Wniosek } from '../types';
import { dodajDni, doIso, dzisIso, formatuj, zIso } from '../lib/daty';
import { czyDzienWolny, pilnosc, type Pilnosc } from '../lib/terminy';
import { Pozostalo, ZnaczekStatusu } from '../components/Znaczki';

type Filtr = 'wszystkie' | 'pilne' | 'w_toku' | Status;
type Wiersz = Wniosek & { lp: number; termin: string; pozostalo: number; pilnosc: Pilnosc };

export default function Kalendarz() {
  const { wnioski, przywrocDaneTestowe } = useMagazyn();
  const dzis = dzisIso();
  const lata = useMemo(
    () => [...new Set([dzis.slice(0, 4), ...wnioski.map((w) => w.dataWplywu.slice(0, 4))])].sort().reverse(),
    [wnioski, dzis],
  );
  const [rok, setRok] = useState(dzis.slice(0, 4));
  const [filtr, setFiltr] = useState<Filtr>('wszystkie');
  const [szukaj, setSzukaj] = useState('');
  const [widok, setWidok] = useState<'tabela' | 'miesiac'>('tabela');

  const wiersze: Wiersz[] = useMemo(
    () =>
      wnioski
        .filter((w) => w.dataWplywu.startsWith(rok))
        .sort((a, b) => a.dataWplywu.localeCompare(b.dataWplywu) || a.numer.localeCompare(b.numer, 'pl', { numeric: true }))
        .map((w, i) => ({ ...w, lp: i + 1, ...pilnosc(w, dzis) })),
    [wnioski, rok, dzis],
  );

  const licz = (f: (w: Wiersz) => boolean) => wiersze.filter(f).length;
  const kafle: { id: Filtr; etykieta: string; liczba: number; klasa?: string }[] = [
    { id: 'wszystkie', etykieta: 'Wszystkie', liczba: wiersze.length },
    { id: 'pilne', etykieta: 'Po terminie / dziś / jutro', liczba: licz((w) => ['po_terminie', 'dzis', 'jutro'].includes(w.pilnosc)), klasa: 'pil-po_terminie' },
    { id: 'w_toku', etykieta: 'W toku', liczba: licz((w) => w.status !== 'odpowiedz_wyslana') },
    { id: 'kwerenda', etykieta: 'Kwerenda', liczba: licz((w) => w.status === 'kwerenda') },
    { id: 'odpowiedz_wyslana', etykieta: 'Odpowiedź wysłana', liczba: licz((w) => w.status === 'odpowiedz_wyslana') },
  ];

  const q = szukaj.trim().toLowerCase();
  const widoczne = wiersze.filter((w) => {
    if (filtr === 'pilne' && !['po_terminie', 'dzis', 'jutro'].includes(w.pilnosc)) return false;
    if (filtr === 'w_toku' && w.status === 'odpowiedz_wyslana') return false;
    if (filtr !== 'wszystkie' && filtr !== 'pilne' && filtr !== 'w_toku' && w.status !== filtr) return false;
    if (q && !`${w.numer} ${w.temat} ${w.wnioskodawca} ${w.inicjaly}`.toLowerCase().includes(q)) return false;
    return true;
  });

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
          <Link className="przycisk glowny" to="/nowy">+ Nowy wniosek</Link>
        </div>
      </div>

      <div className="kafle">
        {kafle.map((k) => (
          <button key={k.id} className={`kafel ${filtr === k.id ? 'wybrany' : ''}`} onClick={() => setFiltr(k.id)}>
            <span className={`liczba ${k.liczba ? k.klasa ?? '' : ''}`}>{k.liczba}</span>
            <span className="maly">{k.etykieta}</span>
          </button>
        ))}
      </div>

      <div className="karta">
        <div className="rzad rozsun" style={{ marginBottom: 12 }}>
          <div className="rzad">
            <div className="zakladki">
              <button className={widok === 'tabela' ? 'aktywna' : ''} onClick={() => setWidok('tabela')}>Tabela</button>
              <button className={widok === 'miesiac' ? 'aktywna' : ''} onClick={() => setWidok('miesiac')}>Kalendarz</button>
            </div>
            <input placeholder="Szukaj: numer, temat, wnioskodawca…" value={szukaj} onChange={(e) => setSzukaj(e.target.value)} style={{ width: 280 }} />
            <select value={STATUSY.some((s) => s.id === filtr) ? filtr : ''} onChange={(e) => setFiltr((e.target.value || 'wszystkie') as Filtr)} style={{ width: 210 }}>
              <option value="">Każdy status</option>
              {STATUSY.map((s) => <option key={s.id} value={s.id}>{s.etykieta}</option>)}
            </select>
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
            <tr key={w.id} className={`p-${w.pilnosc}`} onClick={() => nav(`/sprawa/${w.id}`)}>
              <td>{w.lp}</td>
              <td className="numer nowrap">{w.numer}</td>
              <td className="nowrap">{formatuj(w.dataWplywu)}</td>
              <td>
                <Link to={`/sprawa/${w.id}`} onClick={(e) => e.stopPropagation()} style={{ color: 'inherit', fontWeight: 500, textDecoration: 'none' }}>
                  {w.temat}
                </Link>
                <div className="maly">{w.wnioskodawca}</div>
              </td>
              <td title="Inicjały osoby prowadzącej">{w.inicjaly}</td>
              <td className="nowrap">{formatuj(w.termin)}</td>
              <td className="nowrap"><Pozostalo pilnosc={w.pilnosc} pozostalo={w.pozostalo} /></td>
              <td><ZnaczekStatusu status={w.status} dniKwerendy={w.dniKwerendy} /></td>
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
        <span className="maly">Wnioski pokazane w dniu terminu odpowiedzi (wysłane – w dniu wysyłki).</span>
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
              <Link key={w.id} to={`/sprawa/${w.id}`} className={`chip p-${w.pilnosc}`} title={`${w.numer} – ${w.temat}`}>
                {w.inicjaly} · {w.temat}
              </Link>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}
