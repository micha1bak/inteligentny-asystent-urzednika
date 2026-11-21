import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useMagazyn } from '../magazyn';
import { szukajPodobnych } from '../lib/podobienstwo';
import { proponujWydzialy } from '../lib/wydzialy';
import { JEDNOSTKI, SLOWNIK_WERDYKTOW } from '../dane/referencje';
import { formatuj } from '../lib/daty';

function Pasek({ wartosc }: { wartosc: number }) {
  return (
    <div className="pasek" title={`dopasowanie ${Math.round(wartosc * 100)}%`}>
      <div style={{ width: `${Math.min(100, Math.round(wartosc * 100))}%` }} />
    </div>
  );
}

export function PodobneSprawy({ tekst, pomijajId }: { tekst: string; pomijajId?: string }) {
  const { archiwum, wnioski } = useMagazyn();
  const wyniki = useMemo(() => {
    if (tekst.trim().length < 20) return [];
    const dokumenty = [
      ...archiwum.map((a) => ({
        element: { klucz: a.id, sygnatura: a.sygnatura, data: a.data, wniosek: a.wniosek, odpowiedz: a.odpowiedz, komorka: a.komorka, werdykt: a.werdykt, link: undefined as string | undefined },
        tekst: `${a.wniosek} ${a.odpowiedz}`,
      })),
      ...wnioski
        .filter((w) => w.id !== pomijajId)
        .map((w) => ({
          element: { klucz: w.id, sygnatura: w.numer, data: w.dataWplywu, wniosek: w.temat, odpowiedz: w.odpowiedzi.map((o) => o.tresc).join(' '), komorka: w.wydzialy.join(', '), werdykt: w.werdykt, link: `/sprawa/${w.id}` },
          tekst: `${w.temat} ${w.tresc}`,
        })),
    ];
    return szukajPodobnych(tekst, dokumenty, 5);
  }, [tekst, archiwum, wnioski, pomijajId]);

  return (
    <div className="karta">
      <h2>Podobne sprawy</h2>
      {wyniki.length === 0 ? (
        <p className="maly">Brak podobnych spraw w archiwum{tekst.trim().length < 20 ? ' (za mało treści do porównania)' : ''}.</p>
      ) : (
        <ul className="lista">
          {wyniki.map(({ element: s, wynik, wspolne }) => (
            <li key={s.klucz}>
              <div className="rzad rozsun">
                <span className="numer">{s.link ? <Link to={s.link}>{s.sygnatura}</Link> : s.sygnatura}</span>
                <Pasek wartosc={wynik} />
              </div>
              <div style={{ margin: '4px 0' }}>{s.wniosek}</div>
              <div className="maly">
                {formatuj(s.data)}{s.komorka ? ` · ${s.komorka}` : ''}
                {s.werdykt ? <> · <span title={SLOWNIK_WERDYKTOW[s.werdykt]}>{s.werdykt}</span></> : null}
              </div>
              {s.odpowiedz && (
                <details style={{ marginTop: 6 }}>
                  <summary className="maly">Jak odpowiedziano</summary>
                  <p style={{ margin: '6px 0 0', fontSize: '0.88rem' }}>{s.odpowiedz}</p>
                </details>
              )}
              <div className="maly" style={{ marginTop: 4 }}>wspólne: {wspolne.slice(0, 5).join(', ')}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface WydzialyProps {
  tekst: string;
  wybrane: string[];
  onZmien: (symbole: string[]) => void;
}

export function ProponowaneWydzialy({ tekst, wybrane, onZmien }: WydzialyProps) {
  const { archiwum } = useMagazyn();
  const propozycje = useMemo(() => (tekst.trim().length < 20 ? [] : proponujWydzialy(tekst, JEDNOSTKI, archiwum)), [tekst, archiwum]);
  const przelacz = (s: string) => onZmien(wybrane.includes(s) ? wybrane.filter((x) => x !== s) : [...wybrane, s]);

  return (
    <div className="karta">
      <h2>Do kogo o odpowiedź</h2>
      <p className="maly" style={{ marginTop: -6 }}>Zaznacz jednostki, do których kierujesz zapytanie. Program niczego nie wysyła – tylko zapisuje Twoją decyzję.</p>
      <ul className="lista">
        {propozycje.map((p) => (
          <li key={p.jednostka.symbol}>
            <label style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, color: 'inherit', fontSize: '0.92rem' }}>
              <input type="checkbox" style={{ width: 'auto', marginTop: 3 }} checked={wybrane.includes(p.jednostka.symbol)} onChange={() => przelacz(p.jednostka.symbol)} />
              <span style={{ flex: 1 }}>
                <strong>{p.jednostka.symbol}</strong> – {p.jednostka.nazwa}
                <span className="maly" style={{ display: 'block' }}>{p.powody.join(' · ')}</span>
              </span>
              <Pasek wartosc={Math.min(1, p.wynik * 1.5)} />
            </label>
          </li>
        ))}
      </ul>
      {propozycje.length === 0 && <p className="maly">Brak propozycji – wybierz ręcznie poniżej.</p>}
      <select
        value=""
        onChange={(e) => e.target.value && przelacz(e.target.value)}
        style={{ marginTop: 10 }}
      >
        <option value="">+ dodaj inną jednostkę…</option>
        {JEDNOSTKI.filter((j) => !wybrane.includes(j.symbol)).map((j) => (
          <option key={j.symbol} value={j.symbol}>{j.symbol} – {j.nazwa}</option>
        ))}
      </select>
      {wybrane.filter((s) => !propozycje.some((p) => p.jednostka.symbol === s)).length > 0 && (
        <div className="rzad" style={{ marginTop: 8 }}>
          {wybrane
            .filter((s) => !propozycje.some((p) => p.jednostka.symbol === s))
            .map((s) => (
              <button key={s} className="maly-p" onClick={() => przelacz(s)} title="Usuń">{s} ✕</button>
            ))}
        </div>
      )}
    </div>
  );
}
