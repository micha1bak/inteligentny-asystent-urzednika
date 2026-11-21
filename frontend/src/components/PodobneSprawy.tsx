import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { pobierzPodobne, type WynikPodobnych } from '../lib/api';
import { STATUSY } from '../types';

/**
 * Podobne sprawy z archiwum odpowiedzi i podobne wnioski z ostatniego roku (krok 3 instrukcji UMB).
 * Wyszukiwanie lokalne (TF-IDF), bez AI – dane nie opuszczają komputera.
 */
export default function PodobneSprawy({ tresc, pominId, dataOdniesienia, tytul = 'Podobne sprawy i wnioski', kompaktowo = false }: {
  tresc: string;
  pominId?: string;
  dataOdniesienia?: string;
  tytul?: string;
  kompaktowo?: boolean;
}) {
  const [wynik, setWynik] = useState<WynikPodobnych>();
  const [blad, setBlad] = useState('');

  useEffect(() => {
    if (tresc.trim().length < 10) return;
    const ac = new AbortController();
    const t = setTimeout(() => {
      pobierzPodobne({ tresc, pomin_id: pominId, data_odniesienia: dataOdniesienia || undefined }, ac.signal)
        .then((w) => { setWynik(w); setBlad(''); })
        .catch((e) => { if (!(e instanceof DOMException && e.name === 'AbortError')) setBlad(e instanceof Error ? e.message : String(e)); });
    }, 300);
    return () => { clearTimeout(t); ac.abort(); };
  }, [tresc, pominId, dataOdniesienia]);

  const procent = (p: number) => `${Math.round(p * 100)}%`;
  const etykieta = (s: string) => STATUSY.find((x) => x.id === s)?.etykieta ?? s;
  const pusto = wynik && !wynik.sprawy.length && !wynik.wnioski.length;

  const tresc_ = (
    <>
      {blad && <div className="blad">{blad}</div>}
      {!wynik && !blad && <p className="maly">Szukam podobnych spraw…</p>}
      {pusto && <p className="maly">Brak podobnych spraw w archiwum i wniosków z ostatniego roku.</p>}
      {wynik && wynik.sprawy.length > 0 && (
        <div>
          <div className="maly">Archiwum odpowiedzi</div>
          <ul className="lista-podobnych">
            {wynik.sprawy.map((s) => (
              <li key={s.sygnatura}>
                <span className="podobienstwo" title="Podobieństwo treści">{procent(s.podobienstwo)}</span>{' '}
                <strong>{s.sygnatura}</strong> – {s.wniosek_o_co}
                {!kompaktowo && (
                  <div className="maly">
                    {s.werdykt.replaceAll('_', ' ').toLowerCase()} · {s.komorka_merytoryczna}
                    {s.jaka_odpowiedz && <> · odpowiedź: {s.jaka_odpowiedz.slice(0, 180)}{s.jaka_odpowiedz.length > 180 ? '…' : ''}</>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {wynik && wynik.wnioski.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div className="maly">Wnioski z ostatniego roku</div>
          <ul className="lista-podobnych">
            {wynik.wnioski.map((w) => (
              <li key={w.id}>
                <span className="podobienstwo">{procent(w.podobienstwo)}</span>{' '}
                <Link to={`/wnioski/${w.id}`}>{w.numer}</Link> – {w.temat}
                <span className="maly"> · {w.data_wplywu} · {etykieta(w.status)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );

  if (kompaktowo) return <div className="podobne-kompakt"><div className="maly"><strong>{tytul}</strong></div>{tresc_}</div>;
  return <div className="karta"><h2>{tytul}</h2>{tresc_}</div>;
}
