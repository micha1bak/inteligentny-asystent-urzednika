import { useEffect, useRef, useState } from 'react';
import {
  pobierzJednostki,
  zaproponujWydzial,
  zlozWiadomoscDoWydzialu,
  type JednostkaUmb,
  type PropozycjaWydzialu,
} from '../lib/api';
import { STATUSY, type Status } from '../types';

/**
 * Zapytanie do wydziału: AI (RAG – zakresy kompetencji jednostek UMB + podobne sprawy z archiwum) proponuje
 * do 3 właściwych jednostek, urzędnik wybiera jedną, a aplikacja składa wiadomość przekazującą wniosek
 * (§ 9–11 Zarządzenia Nr 535/2024). Wiadomość urzędnik kopiuje i wysyła ze swojej poczty.
 */
export default function ZapytanieDoWydzialu({ wniosek, status, onOznaczWyslane }: {
  wniosek: { tresc: string; numer: string; data_wplywu: string; temat: string };
  /** aktualny status wniosku – przy „Brak działań” można oznaczyć wysłanie zapytania */
  status: Status;
  onOznaczWyslane: () => Promise<void>;
}) {
  const [jednostki, setJednostki] = useState<JednostkaUmb[]>([]);
  const [propozycja, setPropozycja] = useState<PropozycjaWydzialu>();
  const [wybrana, setWybrana] = useState('');
  const [termin, setTermin] = useState('');
  const [temat, setTemat] = useState('');
  const [tresc, setTresc] = useState('');
  const [recznie, setRecznie] = useState(false);
  const [trwa, setTrwa] = useState(false);
  const [blad, setBlad] = useState('');
  const [skopiowano, setSkopiowano] = useState(false);
  const [oznaczanie, setOznaczanie] = useState(false);
  const przerwij = useRef<AbortController | null>(null);

  const mozna = wniosek.tresc.trim().length >= 20;

  useEffect(() => {
    const ac = new AbortController();
    pobierzJednostki(ac.signal).then(setJednostki).catch(() => {});
    return () => ac.abort();
  }, []);

  async function zaproponuj() {
    przerwij.current?.abort();
    const ac = new AbortController();
    przerwij.current = ac;
    setTrwa(true);
    setBlad('');
    try {
      const p = await zaproponujWydzial(
        { tresc: wniosek.tresc, numer: wniosek.numer, data_wplywu: wniosek.data_wplywu, temat: wniosek.temat },
        ac.signal,
      );
      setPropozycja(p);
      setWybrana(p.jednostki[0]?.nazwa ?? '');
      setTermin('');
      setRecznie(false);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) setBlad(e instanceof Error ? e.message : String(e));
    } finally {
      if (przerwij.current === ac) setTrwa(false);
    }
  }

  // wiadomość składa backend (bez AI) – po każdej zmianie jednostki lub terminu
  useEffect(() => {
    if (!wybrana || recznie) return;
    const ac = new AbortController();
    const t = setTimeout(() => {
      zlozWiadomoscDoWydzialu(
        {
          jednostka: wybrana,
          numer: wniosek.numer || undefined,
          data_wplywu: wniosek.data_wplywu || undefined,
          termin: termin || undefined,
        },
        ac.signal,
      )
        .then((w) => {
          setTemat(w.temat);
          setTresc(w.tresc);
          if (!termin) setTermin(w.termin);
        })
        .catch((e) => {
          if (!(e instanceof DOMException && e.name === 'AbortError')) setBlad(e instanceof Error ? e.message : String(e));
        });
    }, 250);
    return () => {
      clearTimeout(t);
      ac.abort();
    };
  }, [wybrana, termin, recznie, wniosek.numer, wniosek.data_wplywu]);

  async function kopiuj() {
    try {
      await navigator.clipboard.writeText(`Temat: ${temat}\n\n${tresc}\n\n--- Treść wniosku ---\n${wniosek.tresc}`);
      setSkopiowano(true);
      setTimeout(() => setSkopiowano(false), 1500);
    } catch {
      /* brak uprawnień do schowka */
    }
  }

  async function oznacz() {
    setOznaczanie(true);
    setBlad('');
    try {
      await onOznaczWyslane();
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    } finally {
      setOznaczanie(false);
    }
  }

  const proponowane = propozycja?.jednostki ?? [];
  const pozostale = jednostki.filter((j) => !proponowane.some((p) => p.symbol === j.symbol));

  return (
    <div className="karta">
      <div className="rzad rozsun">
        <h2 style={{ margin: 0 }}>Zapytanie do wydziału (AI)</h2>
        <button className={propozycja ? 'maly-p' : 'glowny'} disabled={!mozna || trwa} onClick={() => void zaproponuj()}>
          {trwa ? 'Dobieram wydział…' : propozycja ? 'Zaproponuj ponownie' : 'Zaproponuj wydział'}
        </button>
      </div>
      <p className="maly" style={{ margin: '8px 0 12px' }}>
        AI dobiera komórkę, która posiada żądane informacje (zakresy spraw jednostek UMB i podobne sprawy z archiwum).
        Wybór należy do urzędnika; wiadomość wysyłasz ze swojej poczty.
      </p>
      {!mozna && <p className="maly">Najpierw uzupełnij treść wniosku.</p>}
      {trwa && <div className="postep postep-ciagly"><div /></div>}
      {blad && <div className="blad">{blad}</div>}

      {propozycja && !trwa && (
        <div className="stos" style={{ gap: 12 }}>
          {propozycja.ostrzezenia.map((o) => <div key={o} className="uwaga">{o}</div>)}
          {propozycja.podmiot_poza_umb && (
            <div className="uwaga">
              Informacje najpewniej posiada podmiot spoza Urzędu Miasta: <strong>{propozycja.podmiot_poza_umb}</strong>.
              Rozważ pismo informacyjne ze wskazaniem dysponenta (art. 4 ust. 3 UDIP) zamiast zapytania do wydziału.
            </div>
          )}
          <fieldset className="wybor-wydzialu">
            <legend className="maly">Komórka merytoryczna</legend>
            {proponowane.map((j, i) => (
              <label key={j.symbol} className={`wydzial-opcja${wybrana === j.nazwa ? ' wybrana' : ''}`}>
                <input type="radio" name="wydzial" checked={wybrana === j.nazwa} onChange={() => { setWybrana(j.nazwa); setRecznie(false); }} />
                <span>
                  <strong>{i + 1}. {j.nazwa}</strong>
                  {j.uzasadnienie && <span className="maly"> – {j.uzasadnienie}</span>}
                  <span className="maly wydzial-zakres">{j.zakres}</span>
                </span>
              </label>
            ))}
            <label className="maly">
              Inna jednostka
              <select
                value={proponowane.some((p) => p.nazwa === wybrana) ? '' : wybrana}
                onChange={(e) => { if (e.target.value) { setWybrana(e.target.value); setRecznie(false); } }}
              >
                <option value="">— wybierz z listy —</option>
                {pozostale.map((j) => <option key={j.symbol} value={j.nazwa}>{j.nazwa}</option>)}
              </select>
            </label>
          </fieldset>

          <div className="formularz">
            <label>
              Termin projektu odpowiedzi
              <input type="date" value={termin} onChange={(e) => { setTermin(e.target.value); setRecznie(false); }} />
            </label>
          </div>

          {tresc && (
            <div className="stos" style={{ gap: 6 }}>
              <label>
                Temat wiadomości
                <input value={temat} onChange={(e) => { setTemat(e.target.value); setRecznie(true); }} />
              </label>
              <label>
                Treść wiadomości {recznie && <span className="maly">(edytowana ręcznie – zmiany pól powyżej jej nie nadpiszą)</span>}
                <textarea rows={14} value={tresc} onChange={(e) => { setTresc(e.target.value); setRecznie(true); }} />
              </label>
              <div className="rzad">
                <button className="maly-p" onClick={() => void kopiuj()}>{skopiowano ? 'Skopiowano' : 'Kopiuj wiadomość z wnioskiem'}</button>
                {recznie && <button className="maly-p" onClick={() => setRecznie(false)}>Złóż ponownie z pól</button>}
                {status === 'brak_dzialan' ? (
                  <button className="glowny" disabled={oznaczanie} onClick={() => void oznacz()}>
                    {oznaczanie ? 'Zapisuję…' : 'Oznacz: zapytanie wysłane'}
                  </button>
                ) : (
                  <span className="info-statusu" title="Status zmienisz w karcie „Dane wniosku”">
                    ✓ Status wniosku: {STATUSY.find((s) => s.id === status)?.etykieta ?? status}
                  </span>
                )}
                <span className="maly">model: {propozycja.model}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
