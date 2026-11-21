import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import Kalendarz from './pages/Kalendarz';
import NowyWniosek from './pages/NowyWniosek';

export default function App() {
  return (
    <div className="uklad">
      <aside className="boczny">
        <div className="logo">
          Asystent urzędnika
          <small>Wnioski o informację publiczną · UMB</small>
        </div>
        <nav>
          <NavLink to="/" end>Kalendarz wniosków</NavLink>
          <NavLink to="/nowy">Dodaj wniosek</NavLink>
        </nav>
        <div className="stopka">
          Narzędzie pomocnicze – ostateczną decyzję zawsze podejmuje urzędnik.
          <br />Dane przechowywane lokalnie w tej przeglądarce.
        </div>
      </aside>
      <main className="tresc">
        <Routes>
          <Route path="/" element={<Kalendarz />} />
          <Route path="/nowy" element={<NowyWniosek />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
