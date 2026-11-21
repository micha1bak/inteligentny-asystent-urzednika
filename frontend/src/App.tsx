import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import Kalendarz from './pages/Kalendarz';
import NowyWniosek from './pages/NowyWniosek';
import Sprawa from './pages/Sprawa';
import BazaWiedzy from './pages/BazaWiedzy';

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
          <NavLink to="/nowy">Nowy wniosek</NavLink>
          <NavLink to="/baza">Baza wiedzy</NavLink>
        </nav>
        <div className="stopka">
          Narzędzie pomocnicze – nic nie wysyła samodzielnie. Ostateczną decyzję zawsze podejmuje urzędnik.
          <br />Dane przechowywane lokalnie w tej przeglądarce.
        </div>
      </aside>
      <main className="tresc">
        <Routes>
          <Route path="/" element={<Kalendarz />} />
          <Route path="/nowy" element={<NowyWniosek />} />
          <Route path="/sprawa/:id" element={<Sprawa />} />
          <Route path="/baza" element={<BazaWiedzy />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
