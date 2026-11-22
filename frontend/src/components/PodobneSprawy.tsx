import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { pobierzPodobne, type WynikPodobnych } from '../lib/api';
import { STATUSY } from '../types';

/** Miara 0–1: pokrycie słów sprawy i wniosku (bez nazwisk, adresów i zwrotów grzecznościowych). */
const POZIOMY = [
  { od: 0.45, klasa: 'p-wysokie', opis: 'bardzo podobna' },
  { od: 0.25, klasa: '', opis: 'podobna' },
  { od: 0, klasa: 'p-niskie', opis: 'luźno powiązana' },
];

function Dopasowanie({ wartosc }: { wartosc: number }) {
  const poziom = POZIOMY.find((p) => wartosc >= p.od) ?? POZIOMY[POZIOMY.length - 1];
  return (
    <span className={`podobienstwo ${poziom.klasa}`} title={`Dopasowanie treści: ${poziom.opis}`}>
      {Math.round(wartosc * 100)}%
    </span>
  );
}

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
                <Dopasowanie wartosc={s.podobienstwo} />{' '}
                <strong>{s.sygnatura}</strong> – {s.wniosek_o_co}
                <div className="maly">
                  {s.wydzialy?.length
                    ? <>przekazano do: {s.wydzialy.map((w) => <span key={w.symbol} className="znaczek wydzial" title={w.nazwa}>{w.symbol}</span>)}</>
                    : 'nie przekazano do wydziału'}
                  {s.podmiot_poza_umb && <> · dysponent: {s.podmiot_poza_umb}</>}
                </div>
                {!kompaktowo && (
                  <div className="maly">
                    {s.werdykt.replaceAll('_', ' ').toLowerCase()}
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
                <Dopasowanie wartosc={w.podobienstwo} />{' '}
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
