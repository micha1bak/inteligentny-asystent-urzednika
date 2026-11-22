import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import FormularzSprawy, { brakujacePola } from '../components/FormularzSprawy';
import StrefaPliku from '../components/StrefaPliku';
import { dodajDoArchiwum, pobierzArchiwum, PUSTA_SPRAWA, zaproponujWpis, type Archiwum, type Sprawa } from '../lib/api';
import { zapamietaneInicjaly, zapamietajInicjaly } from '../lib/inicjaly';
import type { WynikOdczytu } from '../lib/parsowanie';

/** Dane przekazywane z kalendarza („Dodaj do archiwum” przy wniosku z wysłaną odpowiedzią). */
export interface ZWniosku {
  sygnatura: string;
  wniosek: string;
  dataOdpowiedzi?: string;
}

interface Dokument {
  nazwa: string;
  tekst: string;
  uwaga?: string;
}

function dokument(wynik: WynikOdczytu, plik: File): Dokument {
  if (wynik.odreczny) return { nazwa: plik.name, tekst: '', uwaga: 'Pismo odręczne – tekst nie został odczytany. Wypełnij wpis ręcznie.' };
  if (!wynik.tekst) return { nazwa: plik.name, tekst: '', uwaga: 'Nie udało się odczytać tekstu z pliku.' };
  return { nazwa: plik.name, tekst: wynik.tekst };
}

export default function NowaSprawaArchiwum() {
  const nav = useNavigate();
  const zWniosku = (useLocation().state as ZWniosku | null) ?? undefined;
  const [archiwum, setArchiwum] = useState<Archiwum>();
  const [wniosek, setWniosek] = useState<Dokument | undefined>(
    zWniosku?.wniosek ? { nazwa: zWniosku.sygnatura, tekst: zWniosku.wniosek } : undefined,
  );
  const [odpowiedz, setOdpowiedz] = useState<Dokument>();
  const [sprawa, setSprawa] = useState<Sprawa>({
    ...PUSTA_SPRAWA,
    sygnatura: zWniosku?.sygnatura ?? '',
    data_odpowiedzi: zWniosku?.dataOdpowiedzi ?? '',
  });
  const [ostrzezenia, setOstrzezenia] = useState<string[]>([]);
  const [autor, setAutor] = useState(zapamietaneInicjaly);
  const [blad, setBlad] = useState('');
  const [trwaPropozycja, setTrwaPropozycja] = useState(false);
  const [trwaZapis, setTrwaZapis] = useState(false);
  const przerwij = useRef<AbortController | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    pobierzArchiwum(ac.signal)
      .then(setArchiwum)
      .catch((e) => !(e instanceof DOMException && e.name === 'AbortError') && setBlad(e instanceof Error ? e.message : String(e)));
    return () => {
      ac.abort();
      przerwij.current?.abort();
    };
  }, []);

  const duplikat = !!archiwum?.sprawy.some((s) => s.sygnatura === sprawa.sygnatura.trim());
  const braki = brakujacePola(sprawa);
  const moznaProponowac = !!wniosek?.tekst && !!odpowiedz?.tekst && !trwaPropozycja;

  async function zaproponuj() {
    if (!wniosek?.tekst || !odpowiedz?.tekst) return;
    przerwij.current?.abort();
    const ac = (przerwij.current = new AbortController());
    setTrwaPropozycja(true);
    setBlad('');
    try {
      const p = await zaproponujWpis({ wniosek: wniosek.tekst, odpowiedz: odpowiedz.tekst, sygnatura: sprawa.sygnatura.trim() }, ac.signal);
      // pola, których model nie ustalił, zostają takie, jak wpisał urzędnik
      setSprawa((s) => ({
        ...s,
        ...Object.fromEntries(Object.entries(p.sprawa).filter(([, v]) => (Array.isArray(v) ? v.length > 0 : v))),
      }));
      setOstrzezenia(p.ostrzezenia);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) setBlad(e instanceof Error ? e.message : String(e));
    } finally {
      if (przerwij.current === ac) setTrwaPropozycja(false);
    }
  }

  async function zapisz() {
    if (!autor.trim()) {
      setBlad('Wpisz swoje inicjały – trafią do historii zmian.');
      return;
    }
    setTrwaZapis(true);
    setBlad('');
    try {
      zapamietajInicjaly(autor.trim());
      await dodajDoArchiwum(sprawa, autor.trim());
      nav('/archiwum');
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
      setTrwaZapis(false);
    }
  }

  return (
    <>
      <div className="rzad rozsun" style={{ marginBottom: 18 }}>
        <div className="rzad">
          <Link className="przycisk maly-p" to="/archiwum">← Archiwum</Link>
          <h1 style={{ margin: 0 }}>Dodaj sprawę do archiwum</h1>
        </div>
      </div>
      <div className="siatka-2">
        <div className="stos">
          <div className="karta">
            <h2>1. Dokumenty sprawy</h2>
            <div className="dwa-pliki">
              <div>
                <h3>Wniosek</h3>
                <StrefaPliku
                  napis={wniosek ? wniosek.nazwa : 'Wybierz plik'}
                  onWczytano={(w, plik) => setWniosek(dokument(w, plik))}
                />
                {wniosek?.uwaga && <div className="uwaga" style={{ marginTop: 8 }}>{wniosek.uwaga}</div>}
              </div>
              <div>
                <h3>Wysłana odpowiedź</h3>
                <StrefaPliku
                  napis="Wybierz plik"
                  onWczytano={(w, plik) => setOdpowiedz(dokument(w, plik))}
                />
                {odpowiedz?.uwaga && <div className="uwaga" style={{ marginTop: 8 }}>{odpowiedz.uwaga}</div>}
              </div>
            </div>
            <div className="rzad" style={{ marginTop: 14 }}>
              <button className="glowny" disabled={!moznaProponowac} onClick={zaproponuj}>
                {trwaPropozycja ? 'Analizuję…' : 'Zaproponuj wpis (AI)'}
              </button>
            </div>
            {trwaPropozycja && (
              <div className="postep postep-ciagly" role="progressbar"><div /></div>
            )}
          </div>

          <div className="karta">
            <h2>2. Wpis do archiwum</h2>
            {ostrzezenia.length > 0 && (
              <div className="uwaga" style={{ marginBottom: 12 }}>
                <strong>Propozycja modelu – sprawdź przed zapisem:</strong>
                <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                  {ostrzezenia.map((o) => <li key={o}>{o}</li>)}
                </ul>
              </div>
            )}
            {archiwum ? (
              <FormularzSprawy sprawa={sprawa} onZmiana={setSprawa} werdykty={archiwum.werdykty} jednostki={archiwum.jednostki} />
            ) : (
              <p className="maly">Wczytuję słownik werdyktów…</p>
            )}
            {duplikat && (
              <div className="uwaga" style={{ marginTop: 12 }}>
                Sprawa {sprawa.sygnatura} jest już w archiwum – <Link to="/archiwum">zmień istniejący wpis</Link> zamiast dodawać nowy.
              </div>
            )}
            <div className="rzad" style={{ marginTop: 14, alignItems: 'flex-end' }}>
              <label style={{ width: 110 }}>
                Twoje inicjały
                <input value={autor} maxLength={4} onChange={(e) => setAutor(e.target.value.toUpperCase())} />
              </label>
              <button className="glowny" disabled={trwaZapis || braki.length > 0 || duplikat || !archiwum} onClick={zapisz}>
                Zatwierdź i zapisz w archiwum
              </button>
            </div>
            {braki.length > 0 && <p className="maly">Wymagane: {braki.join(', ')}.</p>}
            {blad && <div className="blad" style={{ marginTop: 12 }}>{blad}</div>}
          </div>
        </div>

        <div className="stos">
          <PodgladDokumentu tytul="Treść wniosku" dokument={wniosek} />
          <PodgladDokumentu tytul="Treść odpowiedzi" dokument={odpowiedz} />
        </div>
      </div>
    </>
  );
}

function PodgladDokumentu({ tytul, dokument }: { tytul: string; dokument?: Dokument }) {
  return (
    <div className="karta">
      <h2>{tytul}</h2>
      {dokument?.tekst ? (
        <div className="pole-tekstu" style={{ maxHeight: 260 }}>{dokument.tekst}</div>
      ) : (
        <p className="maly">{dokument ? 'Brak odczytanego tekstu.' : 'Pojawi się po wgraniu pliku.'}</p>
      )}
    </div>
  );
}
