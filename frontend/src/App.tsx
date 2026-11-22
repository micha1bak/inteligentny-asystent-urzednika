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

export default function App() {
  const { pathname } = useLocation();
  const { sesja, ladowanie, wyloguj } = useSesja();
  const aktywneWnioski = pathname === '/' || pathname.startsWith('/wnioski/');

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
      </div>
    </DostawcaMagazynu>
  );
}
