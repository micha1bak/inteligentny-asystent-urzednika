import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PodgladPliku from '../components/PodgladPliku';
import { ROZSZERZENIA_WNIOSKU, type WniosekDoZapisu } from '../lib/api';
import { dzisIso } from '../lib/daty';
import { zapamietajInicjaly, zapamietaneInicjaly } from '../lib/inicjaly';
import { odczytajWniosek, wyciagnijMetadane } from '../lib/parsowanie';
import { useMagazyn } from '../magazyn';

interface PozycjaPliku {
  lokalneId: string;
  plik: File;
  stan: 'oczekuje' | 'czyta' | 'gotowy' | 'odreczny' | 'blad';
  blad?: string;
  tresc: string;
  temat: string;
  wnioskodawca: string;
  kontakt: string;
}

function nazwaBezRozszerzenia(nazwa: string): string {
  return nazwa.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim() || nazwa;
}

export default function NowyWniosek() {
  const { dodajWniosek, dodajWnioskiWsadowo, nastepnyNumer } = useMagazyn();
  const nav = useNavigate();
  const wejscie = useRef<HTMLInputElement>(null);
  const przetwarzane = useRef(false);
  const przerwij = useRef<AbortController | null>(null);

  const [dataWplywu, setDataWplywu] = useState(dzisIso);
  const [inicjaly, setInicjaly] = useState(zapamietaneInicjaly);
  const [aktywna, setAktywna] = useState(false);
  const [pozycje, setPozycje] = useState<PozycjaPliku[]>([]);
  const [podglad, setPodglad] = useState<File | null>(null);
  const [trwaZapis, setTrwaZapis] = useState(false);
  const [blad, setBlad] = useState('');

  useEffect(() => () => przerwij.current?.abort(), []);

  useEffect(() => {
    if (przetwarzane.current) return;
    const nastepna = pozycje.find((p) => p.stan === 'oczekuje');
    if (!nastepna) return;

    przetwarzane.current = true;
    const ac = new AbortController();
    przerwij.current = ac;

    setPozycje((prev) => prev.map((p) => (p.lokalneId === nastepna.lokalneId ? { ...p, stan: 'czyta' } : p)));

    (async () => {
      try {
        const wynik = await odczytajWniosek(nastepna.plik, ac.signal);
        if (wynik.odreczny) {
          setPozycje((prev) =>
            prev.map((p) =>
              p.lokalneId === nastepna.lokalneId
                ? { ...p, stan: 'odreczny', tresc: '', temat: nazwaBezRozszerzenia(p.plik.name) }
                : p,
            ),
          );
          return;
        }
        const m = wynik.tekst ? wyciagnijMetadane(wynik.tekst) : null;
        setPozycje((prev) =>
          prev.map((p) =>
            p.lokalneId === nastepna.lokalneId
              ? {
                  ...p,
                  stan: 'gotowy',
                  tresc: wynik.tekst,
                  temat: m?.temat || nazwaBezRozszerzenia(p.plik.name),
                  wnioskodawca: m?.wnioskodawca ?? '',
                  kontakt: m?.kontakt ?? '',
                }
              : p,
          ),
        );
      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        const msg = e instanceof Error ? e.message : String(e);
        setPozycje((prev) =>
          prev.map((p) => (p.lokalneId === nastepna.lokalneId ? { ...p, stan: 'blad', blad: msg } : p)),
        );
      } finally {
        if (przerwij.current === ac) przerwij.current = null;
        przetwarzane.current = false;
      }
    })();
  }, [pozycje]);

  function dodajPliki(lista: FileList | null) {
    if (!lista || lista.length === 0) return;
    setBlad('');
    const nowe: PozycjaPliku[] = Array.from(lista).map((plik) => ({
      lokalneId: crypto.randomUUID(),
      plik,
      stan: 'oczekuje',
      tresc: '',
      temat: nazwaBezRozszerzenia(plik.name),
      wnioskodawca: '',
      kontakt: '',
    }));
    setPozycje((prev) => [...prev, ...nowe]);
  }

  function usunPozycje(lokalneId: string) {
    setPozycje((prev) => prev.filter((p) => p.lokalneId !== lokalneId));
  }

  const wTrakcie = pozycje.some((p) => p.stan === 'oczekuje' || p.stan === 'czyta');
  const gotowe = pozycje.filter((p) => p.stan === 'gotowy' || p.stan === 'odreczny');
  const rok = dataWplywu.slice(0, 4) || dzisIso().slice(0, 4);

  async function zapiszWszystkie() {
    if (!gotowe.length || wTrakcie) return;
    setTrwaZapis(true);
    setBlad('');
    try {
      const ini = inicjaly.trim().toUpperCase();
      zapamietajInicjaly(ini);
      const wsad: WniosekDoZapisu[] = gotowe.map((p) => ({
        dataWplywu,
        temat: p.temat,
        wnioskodawca: p.wnioskodawca,
        kontakt: p.kontakt || undefined,
        inicjaly: ini,
        tresc: p.tresc,
        status: 'brak_dzialan',
        nazwaPliku: p.plik.name,
      }));
      await dodajWnioskiWsadowo(wsad);
      nav('/');
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
      setTrwaZapis(false);
    }
  }

  async function dodajBezPliku() {
    setTrwaZapis(true);
    setBlad('');
    try {
      const ini = inicjaly.trim().toUpperCase();
      zapamietajInicjaly(ini);
      const utworzony = await dodajWniosek({
        dataWplywu,
        temat: 'Nowy wniosek',
        wnioskodawca: '',
        inicjaly: ini,
        tresc: '',
        status: 'brak_dzialan',
      });
      nav(`/wnioski/${encodeURIComponent(utworzony.id)}`);
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
      setTrwaZapis(false);
    }
  }

  let indeksNumeru = 0;

  return (
    <>
      <div className="rzad rozsun" style={{ marginBottom: 18 }}>
        <h1>Dodaj wniosek</h1>
        <button disabled={trwaZapis} onClick={() => void dodajBezPliku()}>
          Dodaj bez pliku
        </button>
      </div>

      <div className="stos">
        <div className="karta">
          <div className="rzad" style={{ marginBottom: 14 }}>
            <label style={{ width: 170 }}>
              Data wpływu
              <input type="date" value={dataWplywu} onChange={(e) => setDataWplywu(e.target.value)} />
            </label>
            <label style={{ width: 120 }}>
              Inicjały
              <input value={inicjaly} maxLength={4} onChange={(e) => setInicjaly(e.target.value.toUpperCase())} />
            </label>
          </div>

          <div
            className={`strefa-upuszczania ${aktywna ? 'aktywna' : ''} ${wTrakcie ? 'zajeta' : ''}`}
            role="button"
            tabIndex={0}
            aria-label="Wybierz lub upuść pliki"
            onClick={() => wejscie.current?.click()}
            onKeyDown={(e) => {
              if (e.target !== e.currentTarget || (e.key !== 'Enter' && e.key !== ' ')) return;
              e.preventDefault();
              wejscie.current?.click();
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setAktywna(true);
            }}
            onDragLeave={() => setAktywna(false)}
            onDrop={(e) => {
              e.preventDefault();
              setAktywna(false);
              dodajPliki(e.dataTransfer.files);
            }}
          >
            <strong>Wybierz lub upuść pliki</strong>
            <div className="maly" style={{ marginTop: 4 }}>{ROZSZERZENIA_WNIOSKU.join(', ')}</div>
          </div>

          <input
            ref={wejscie}
            type="file"
            multiple
            hidden
            accept={ROZSZERZENIA_WNIOSKU.join(',')}
            onChange={(e) => {
              dodajPliki(e.target.files);
              e.target.value = '';
            }}
          />
        </div>

        {pozycje.length > 0 && (
          <div className="karta">
            <div className="rzad rozsun" style={{ marginBottom: 12 }}>
              <h2 style={{ margin: 0 }}>Pliki do dodania ({pozycje.length})</h2>
              <button className="maly-p" disabled={trwaZapis || wTrakcie} onClick={() => setPozycje([])}>
                Wyczyść listę
              </button>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Nr wniosku</th>
                    <th>Plik</th>
                    <th>Temat</th>
                    <th>Wnioskodawca</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pozycje.map((p) => {
                    const numer = p.stan === 'blad' ? '—' : nastepnyNumer(rok, indeksNumeru++);
                    return (
                      <tr key={p.lokalneId}>
                        <td className="numer nowrap">{numer}</td>
                        <td className="nowrap">
                          <span>{p.plik.name}</span>{' '}
                          <button className="maly-p" onClick={() => setPodglad(p.plik)}>Podgląd</button>
                        </td>
                        <td>
                          {p.temat}
                          {p.blad && <div className="maly" style={{ color: 'var(--czerwony)' }}>{p.blad}</div>}
                        </td>
                        <td>{p.wnioskodawca || <span className="maly">—</span>}</td>
                        <td className="nowrap">
                          <StatusPliku stan={p.stan} />
                        </td>
                        <td className="nowrap">
                          <button
                            className="maly-p"
                            disabled={p.stan === 'czyta' || trwaZapis}
                            onClick={() => usunPozycje(p.lokalneId)}
                            aria-label={`Usuń ${p.plik.name}`}
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {blad && <div className="blad" style={{ marginTop: 12 }}>{blad}</div>}

            <div className="rzad" style={{ marginTop: 14 }}>
              <button
                className="glowny"
                disabled={trwaZapis || wTrakcie || gotowe.length === 0 || !dataWplywu}
                onClick={() => void zapiszWszystkie()}
              >
                {trwaZapis
                  ? 'Zapisywanie…'
                  : gotowe.length === 1
                    ? 'Zapisz wniosek'
                    : `Zapisz wnioski (${gotowe.length})`}
              </button>
            </div>
          </div>
        )}
      </div>

      {podglad && <PodgladPliku plik={podglad} onZamknij={() => setPodglad(null)} />}
    </>
  );
}

function StatusPliku({ stan }: { stan: PozycjaPliku['stan'] }) {
  if (stan === 'oczekuje') return <span className="znaczek s-brak_dzialan">Oczekuje</span>;
  if (stan === 'czyta') return <span className="znaczek s-zapytania_wyslane">Odczytywanie…</span>;
  if (stan === 'gotowy') return <span className="znaczek s-odpowiedz_wyslana">Gotowy</span>;
  if (stan === 'odreczny') return <span className="znaczek s-odpowiedz_przygotowana">Pismo odręczne</span>;
  return <span className="znaczek w-nie">Błąd</span>;
}
