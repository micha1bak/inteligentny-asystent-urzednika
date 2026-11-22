import { useEffect, useState } from 'react';
import Anonimizacja from './pages/Anonimizacja';
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import logoBydgoszcz from './assets/logoBydgoszcz.png';
import { DostawcaMagazynu } from './magazyn';
import { useSesja } from './sesja';
import Wnioski from './pages/Wnioski';
import SzczegolyWniosku from './pages/SzczegolyWniosku';
import NowyWniosek from './pages/NowyWniosek';
import Archiwum from './pages/Archiwum';
import NowaSprawaArchiwum from './pages/NowaSprawaArchiwum';
import BazaWiedzy from './pages/BazaWiedzy';
import Logowanie from './pages/Logowanie';

const KLUCZ_CZCIONKI = 'asystent.rozmiarTekstu';
const KLUCZ_KONTRASTU = 'asystent.wysokiKontrast';
const DOMYSLNY_ROZMIAR = 15;
const MIN_ROZMIAR = 11;
const MAKS_ROZMIAR = 23;
const KROK_ROZMIARU = 2;

function wczytajRozmiarTekstu(): number {
  try {
    const v = Number(localStorage.getItem(KLUCZ_CZCIONKI));
    if (Number.isFinite(v) && v >= MIN_ROZMIAR && v <= MAKS_ROZMIAR) return v;
  } catch {
    /* brak dostępu do localStorage */
  }
  return DOMYSLNY_ROZMIAR;
}

function wczytajKontrast(): boolean {
  try {
    return localStorage.getItem(KLUCZ_KONTRASTU) === '1';
  } catch {
    return false;
  }
}

export default function App() {
  const { pathname } = useLocation();
  const { sesja, ladowanie, wyloguj } = useSesja();
  const [rozmiarTekstu, setRozmiarTekstu] = useState(wczytajRozmiarTekstu);
  const [wysokiKontrast, setWysokiKontrast] = useState(wczytajKontrast);
  const [pokazNaGore, setPokazNaGore] = useState(false);
  const aktywneWnioski = pathname === '/' || pathname.startsWith('/wnioski/');

  useEffect(() => {
    document.documentElement.style.fontSize = `${rozmiarTekstu}px`;
    try {
      localStorage.setItem(KLUCZ_CZCIONKI, String(rozmiarTekstu));
    } catch {
      /* brak dostępu do localStorage */
    }
  }, [rozmiarTekstu]);

  useEffect(() => {
    document.documentElement.classList.toggle('wysoki-kontrast', wysokiKontrast);
    try {
      localStorage.setItem(KLUCZ_KONTRASTU, wysokiKontrast ? '1' : '0');
    } catch {
      /* brak dostępu do localStorage */
    }
  }, [wysokiKontrast]);

  useEffect(() => {
    const sprawdzPrzewiniecie = () => setPokazNaGore(window.scrollY > 300);
    sprawdzPrzewiniecie();
    window.addEventListener('scroll', sprawdzPrzewiniecie, { passive: true });
    return () => window.removeEventListener('scroll', sprawdzPrzewiniecie);
  }, []);

  function zmienRozmiar(delta: number) {
    setRozmiarTekstu((r) => Math.min(MAKS_ROZMIAR, Math.max(MIN_ROZMIAR, r + delta)));
  }

  if (ladowanie) {
    return (
      <div className="logowanie-ekran">
        <div className="karta"><p className="maly" style={{ margin: 0 }}>Sprawdzam sesję…</p></div>
      </div>
    );
  }

  if (!sesja) {
    return <Logowanie />;
  }

  return (
    <DostawcaMagazynu>
      <div className="uklad">
        <aside className="boczny">
          <div className="logo">Asystent urzędnika</div>
          <div className="boczny-logo">
            <img src={logoBydgoszcz} alt="Bydgoszcz" />
          </div>
          <nav>
            <NavLink to="/" end className={() => (aktywneWnioski ? 'active' : '')}>Wnioski</NavLink>
            <NavLink to="/nowy">Dodaj wniosek</NavLink>
            <NavLink to="/archiwum" end>Archiwum odpowiedzi</NavLink>
            <NavLink to="/baza-wiedzy">Baza wiedzy</NavLink>
            <NavLink to="/anonimizacja">Anonimizacja dokumentu</NavLink>
          </nav>
          <div className="boczny-czcionka" role="group" aria-label="Rozmiar tekstu">
            <span className="boczny-czcionka-opis">Rozmiar tekstu</span>
            <div className="boczny-czcionka-przyciski">
              <button
                type="button"
                className="boczny-przycisk"
                disabled={rozmiarTekstu <= MIN_ROZMIAR}
                onClick={() => zmienRozmiar(-KROK_ROZMIARU)}
                title="Zmniejsz tekst"
                aria-label="Zmniejsz tekst"
              >
                A−
              </button>
              <button
                type="button"
                className="boczny-przycisk"
                disabled={rozmiarTekstu >= MAKS_ROZMIAR}
                onClick={() => zmienRozmiar(KROK_ROZMIARU)}
                title="Powiększ tekst"
                aria-label="Powiększ tekst"
              >
                A+
              </button>
            </div>
            {rozmiarTekstu !== DOMYSLNY_ROZMIAR && (
              <button
                type="button"
                className="boczny-przycisk boczny-reset-czcionki"
                onClick={() => setRozmiarTekstu(DOMYSLNY_ROZMIAR)}
                title="Przywróć domyślny rozmiar tekstu"
              >
                Domyślny rozmiar
              </button>
            )}
            <button
              type="button"
              className={`boczny-przycisk boczny-kontrast${wysokiKontrast ? ' aktywny' : ''}`}
              aria-pressed={wysokiKontrast}
              onClick={() => setWysokiKontrast((k) => !k)}
              title="Przełącz tryb wysokiego kontrastu (WCAG)"
            >
              {wysokiKontrast ? '◐ Zwykły widok' : '◐ Duży kontrast'}
            </button>
          </div>
          <div className="boczny-sesja">
            <div className="boczny-sesja-tytul">Zalogowano:</div>
            <div className="boczny-sesja-pole">
              <span>Identyfikator urzędnika:</span>
              <strong>{sesja.id_u}</strong>
            </div>
            {sesja.inicjaly && <div>Inicjały (Os.): <strong>{sesja.inicjaly}</strong></div>}
            <button type="button" className="boczny-wyloguj" onClick={() => void wyloguj()}>
              Wyloguj
            </button>
          </div>
        </aside>
        <main className="tresc">
          <Routes>
            <Route path="/" element={<Wnioski />} />
            <Route path="/wnioski/:id" element={<SzczegolyWniosku />} />
            <Route path="/nowy" element={<NowyWniosek />} />
            <Route path="/archiwum" element={<Archiwum />} />
            <Route path="/archiwum/nowa" element={<NowaSprawaArchiwum />} />
            <Route path="/baza-wiedzy" element={<BazaWiedzy />} />
            <Route path="/anonimizacja" element={<Anonimizacja />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        {pokazNaGore && (
          <button
            type="button"
            className="przycisk-na-gore glowny"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            aria-label="Wróć na górę strony"
            title="Wróć na górę strony"
          >
            ↑ Na górę
          </button>
        )}
      </div>
    </DostawcaMagazynu>
  );
}
