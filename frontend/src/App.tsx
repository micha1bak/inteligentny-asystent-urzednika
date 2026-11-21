import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Wnioski from './pages/Wnioski';
import SzczegolyWniosku from './pages/SzczegolyWniosku';
import NowyWniosek from './pages/NowyWniosek';
import Archiwum from './pages/Archiwum';
import NowaSprawaArchiwum from './pages/NowaSprawaArchiwum';

export default function App() {
  const { pathname } = useLocation();
  const aktywneWnioski = pathname === '/' || pathname.startsWith('/wnioski/');

  return (
    <div className="uklad">
      <aside className="boczny">
        <div className="logo">Asystent urzędnika</div>
        <nav>
          <NavLink to="/" end className={() => (aktywneWnioski ? 'active' : '')}>Wnioski</NavLink>
          <NavLink to="/nowy">Dodaj wniosek</NavLink>
          <NavLink to="/archiwum" end>Archiwum odpowiedzi</NavLink>
        </nav>
      </aside>
      <main className="tresc">
        <Routes>
          <Route path="/" element={<Wnioski />} />
          <Route path="/wnioski/:id" element={<SzczegolyWniosku />} />
          <Route path="/nowy" element={<NowyWniosek />} />
          <Route path="/archiwum" element={<Archiwum />} />
          <Route path="/archiwum/nowa" element={<NowaSprawaArchiwum />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
