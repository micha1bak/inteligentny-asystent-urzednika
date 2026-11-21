import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { zastosujUkrycia, type Sugestia, type Ukrycie } from '../lib/anonimizacja';
import {
  pobierzJednostki,
  sugestieAnonimizacji,
  zaproponujWydzial,
  zlozWiadomoscDoWydzialu,
  type JednostkaUmb,
  type PropozycjaWydzialu,
} from '../lib/api';
import type { DoAnonimizacji } from '../pages/Anonimizacja';
import { STATUSY, type Status } from '../types';
import AnonimizacjaTekstu from './AnonimizacjaTekstu';

interface ZapisanySzkic {
  propozycja?: PropozycjaWydzialu;
  termin: string;
  temat: string;
  tresc: string;
  recznie: boolean;
}

function wczytajSzkic(klucz: string): ZapisanySzkic | null {
  try {
    const surowy = sessionStorage.getItem(klucz);
    return surowy ? (JSON.parse(surowy) as ZapisanySzkic) : null;
  } catch {
    return null;
  }
}

/**
 * Zapytanie do wydziału: AI (RAG – zakresy kompetencji jednostek UMB + podobne sprawy z archiwum) proponuje
 * do 3 właściwych jednostek, urzędnik wybiera jedną, a aplikacja składa wiadomość przekazującą wniosek
 * (§ 9–11 Zarządzenia Nr 535/2024). Wiadomość urzędnik kopiuje lub przekierowuje do anonimizacji (DOCX / TXT).
 */
export default function ZapytanieDoWydzialu({
  wniosekId,
  wniosek,
  wybranyWydzial,
  onWybierzWydzial,
  status,
  onOznaczWyslane,
}: {
  wniosekId: string;
  wniosek: { tresc: string; numer: string; data_wplywu: string; temat: string; wnioskodawca?: string; kontakt?: string };
  wybranyWydzial: string;
  onWybierzWydzial: (nazwa: string) => void;
  /** aktualny status wniosku – przy „Brak działań” można oznaczyć wysłanie zapytania */
  status: Status;
  onOznaczWyslane: () => Promise<void>;
}) {
  const kluczSzkicu = `asystent-urzednika.zapytanie.${wniosekId}`;
  const szkic = useMemo(() => wczytajSzkic(kluczSzkicu), [kluczSzkicu]);

  const [jednostki, setJednostki] = useState<JednostkaUmb[]>([]);
  const [propozycja, setPropozycja] = useState<PropozycjaWydzialu | undefined>(szkic?.propozycja);
  const [termin, setTermin] = useState(szkic?.termin ?? '');
  const [temat, setTemat] = useState(szkic?.temat ?? '');
  const [tresc, setTresc] = useState(szkic?.tresc ?? '');
  const [recznie, setRecznie] = useState(szkic?.recznie ?? false);
  const [trwa, setTrwa] = useState(false);
  const [blad, setBlad] = useState('');
  const [skopiowano, setSkopiowano] = useState(false);
  const [oznaczanie, setOznaczanie] = useState(false);
  const [wykryteDane, setWykryteDane] = useState<Sugestia[]>([]);
  const [trybAnonimizacji, setTrybAnonimizacji] = useState(false);
  const [ukrycia, setUkrycia] = useState<Ukrycie[]>([]);
  const przerwij = useRef<AbortController | null>(null);

  const mozna = wniosek.tresc.trim().length >= 20;

  useEffect(() => {
    const ac = new AbortController();
    pobierzJednostki(ac.signal).then(setJednostki).catch(() => {});
    return () => ac.abort();
  }, []);

  useEffect(() => {
    if (!propozycja) return;
    try {
      const dane: ZapisanySzkic = { propozycja, termin, temat, tresc, recznie };
      sessionStorage.setItem(kluczSzkicu, JSON.stringify(dane));
    } catch {
      /* brak dostępu do sessionStorage */
    }
  }, [kluczSzkicu, propozycja, termin, temat, tresc, recznie]);

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
      onWybierzWydzial(p.jednostki[0]?.nazwa ?? '');
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
    if (!wybranyWydzial || recznie) return;
    const ac = new AbortController();
    const t = setTimeout(() => {
      zlozWiadomoscDoWydzialu(
        {
          jednostka: wybranyWydzial,
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
  }, [wybranyWydzial, termin, recznie, wniosek.numer, wniosek.data_wplywu]);

  const pelnaWiadomosc = useMemo(
    () =>
      [
        temat ? `Temat: ${temat}` : '',
        tresc,
        wniosek.tresc.trim() ? `--- Treść wniosku ---\n${wniosek.tresc}` : '',
      ]
        .filter(Boolean)
        .join('\n\n'),
    [temat, tresc, wniosek.tresc],
  );

  const dodatkoweFrazy = useMemo(
    () => [wniosek.wnioskodawca ?? '', wniosek.kontakt ?? ''].map((s) => s.trim()).filter(Boolean),
    [wniosek.wnioskodawca, wniosek.kontakt],
  );

  // lokalne wykrywanie danych wrażliwych w treści wiadomości i załączonego wniosku (bez AI)
  useEffect(() => {
    if (!tresc.trim()) {
      setWykryteDane([]);
      return;
    }
    const ac = new AbortController();
    const timer = setTimeout(() => {
      sugestieAnonimizacji(pelnaWiadomosc, dodatkoweFrazy, ac.signal)
        .then((lista) => {
          const widziane = new Set<string>();
          setWykryteDane(
            lista.filter((s) => {
              if (widziane.has(s.tekst)) return false;
              widziane.add(s.tekst);
              return true;
            }),
          );
        })
        .catch(() => {});
    }, 300);
    return () => {
      clearTimeout(timer);
      ac.abort();
    };
  }, [pelnaWiadomosc, tresc, dodatkoweFrazy]);

  const nazwaPlikuAnon = wniosek.numer
    ? `${wniosek.numer.replace(/[\\/:*?"<>|\s]+/g, '_')}_zapytanie`
    : 'zapytanie_do_wydzialu';

  const stanAnonimizacji: DoAnonimizacji = {
    tekst: pelnaWiadomosc,
    nazwa: nazwaPlikuAnon,
    dodatkowe: dodatkoweFrazy,
    ukrycia,
    powrot: `/wnioski/${wniosekId}`,
    etykietaPowrotu: wniosek.numer ? `← Wróć do wniosku ${wniosek.numer}` : '← Wróć do wniosku',
  };

  const liczbaUkrytych = ukrycia.filter((u) => u.stan === 'ukryte').length;

  async function kopiuj() {
    try {
      await navigator.clipboard.writeText(zastosujUkrycia(pelnaWiadomosc, ukrycia));
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
      {!mozna && <p className="maly" style={{ marginTop: 8 }}>Najpierw uzupełnij treść wniosku.</p>}
      {trwa && <div className="postep postep-ciagly" style={{ marginTop: 10 }}><div /></div>}
      {blad && <div className="blad" style={{ marginTop: 10 }}>{blad}</div>}

      {propozycja && !trwa && (
        <div className="stos" style={{ gap: 12, marginTop: 12 }}>
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
              <label key={j.symbol} className={`wydzial-opcja${wybranyWydzial === j.nazwa ? ' wybrana' : ''}`}>
                <input
                  type="radio"
                  name={`wydzial-${wniosekId}`}
                  checked={wybranyWydzial === j.nazwa}
                  onChange={() => {
                    onWybierzWydzial(j.nazwa);
                    setRecznie(false);
                  }}
                />
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
                value={proponowane.some((p) => p.nazwa === wybranyWydzial) ? '' : wybranyWydzial}
                onChange={(e) => {
                  if (e.target.value) {
                    onWybierzWydzial(e.target.value);
                    setRecznie(false);
                  }
                }}
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
              <div>
                <div className="rzad rozsun" style={{ marginBottom: 4 }}>
                  <span className="maly">
                    Treść wiadomości {recznie && '(edytowana ręcznie – zmiany pól powyżej jej nie nadpiszą)'}
                    {liczbaUkrytych > 0 && ` · ukryto danych: ${liczbaUkrytych}`}
                  </span>
                  <div className="rzad" style={{ gap: 6 }}>
                    <button
                      type="button"
                      className={trybAnonimizacji ? 'glowny maly-p' : `maly-p${wykryteDane.length > 0 ? ' podstawa-przycisk' : ''}`}
                      onClick={() => setTrybAnonimizacji((t) => !t)}
                    >
                      {trybAnonimizacji
                        ? 'Wróć do edycji treści'
                        : wykryteDane.length > 0
                          ? `Anonimizuj tutaj (${wykryteDane.length})`
                          : 'Anonimizuj tutaj'}
                    </button>
                    <Link className="przycisk maly-p" to="/anonimizacja" state={stanAnonimizacji}>
                      Panel anonimizacji →
                    </Link>
                  </div>
                </div>
                {trybAnonimizacji ? (
                  <AnonimizacjaTekstu
                    tekst={pelnaWiadomosc}
                    nazwa={nazwaPlikuAnon}
                    dodatkowe={dodatkoweFrazy}
                    ukrycia={ukrycia}
                    onZmianaUkryc={setUkrycia}
                  />
                ) : (
                  <textarea rows={14} value={tresc} onChange={(e) => { setTresc(e.target.value); setRecznie(true); }} />
                )}
              </div>
              {!trybAnonimizacji && wykryteDane.length > 0 && (
                <div className="uwaga">
                  Wykryto potencjalne dane wrażliwe ({wykryteDane.length}):{' '}
                  <strong>
                    {wykryteDane.slice(0, 5).map((d) => `${d.tekst} (${d.rodzaj})`).join(', ')}
                    {wykryteDane.length > 5 ? '…' : ''}
                  </strong>
                  . Możesz je ukryć bezpośrednio tutaj (przycisk <strong>Anonimizuj tutaj</strong>) albo{' '}
                  <Link to="/anonimizacja" state={stanAnonimizacji}>
                    w panelu anonimizacji (DOCX / TXT)
                  </Link>
                  .
                </div>
              )}
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
