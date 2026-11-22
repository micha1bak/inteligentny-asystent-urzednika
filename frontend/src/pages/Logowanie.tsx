import { useState, type FormEvent } from 'react';
import logoBydgoszcz from '../assets/logoBydgoszcz.png';
import { useSesja } from '../sesja';

export default function Logowanie() {
  const { zaloguj, zarejestruj } = useSesja();
  const [tryb, setTryb] = useState<'logowanie' | 'rejestracja'>('logowanie');
  const [idU, setIdU] = useState('');
  const [inicjaly, setInicjaly] = useState('');
  const [haslo, setHaslo] = useState('');
  const [trwa, setTrwa] = useState(false);
  const [blad, setBlad] = useState('');

  async function wyslij(e: FormEvent) {
    e.preventDefault();
    setBlad('');
    setTrwa(true);
    try {
      if (tryb === 'logowanie') await zaloguj(idU.trim(), haslo);
      else await zarejestruj(idU.trim(), inicjaly.trim(), haslo);
    } catch (err) {
      setBlad(err instanceof Error ? err.message : String(err));
    } finally {
      setTrwa(false);
    }
  }

  return (
    <div className="logowanie-ekran">
      <div className="karta logowanie-karta">
        <div className="logowanie-logo">
          <img src={logoBydgoszcz} alt="Bydgoszcz" />
        </div>
        <h1 style={{ textAlign: 'center', marginBottom: 4 }}>Asystent urzędnika</h1>
        <p className="maly" style={{ textAlign: 'center', margin: '0 0 18px' }}>
          {tryb === 'logowanie'
            ? 'Podaj identyfikator urzędnika oraz hasło.'
            : 'Dodaj nowe konto urzędnika w lokalnej bazie.'}
        </p>

        <form className="stos" style={{ gap: 12 }} onSubmit={(e) => void wyslij(e)}>
          <label>
            Identyfikator urzędnika
            <input
              value={idU}
              onChange={(e) => setIdU(e.target.value.toUpperCase())}
              placeholder="np. UMB-001"
              minLength={3}
              maxLength={32}
              autoComplete="username"
              autoFocus
              required
            />
          </label>
          {tryb === 'rejestracja' && (
            <label>
              Inicjały (Os.)
              <input
                value={inicjaly}
                onChange={(e) => setInicjaly(e.target.value.toUpperCase())}
                placeholder="np. JK"
                minLength={2}
                maxLength={6}
                required
              />
            </label>
          )}
          <label>
            Hasło
            <input
              type="password"
              value={haslo}
              onChange={(e) => setHaslo(e.target.value)}
              placeholder="Wpisz hasło"
              minLength={4}
              autoComplete={tryb === 'logowanie' ? 'current-password' : 'new-password'}
              required
            />
          </label>

          {blad && <div className="blad">{blad}</div>}

          <button
            type="submit"
            className="glowny"
            style={{ justifyContent: 'center' }}
            disabled={trwa || !idU.trim() || !haslo || (tryb === 'rejestracja' && inicjaly.trim().length < 2)}
          >
            {trwa
              ? tryb === 'logowanie'
                ? 'Logowanie…'
                : 'Tworzenie konta…'
              : tryb === 'logowanie'
                ? 'Zaloguj się'
                : 'Utwórz konto i zaloguj'}
          </button>
        </form>

        <div className="rzad" style={{ marginTop: 14, justifyContent: 'center' }}>
          <button
            type="button"
            className="maly-p"
            onClick={() => {
              setTryb((t) => (t === 'logowanie' ? 'rejestracja' : 'logowanie'));
              setBlad('');
            }}
          >
            {tryb === 'logowanie' ? 'Dodaj konto urzędnika' : '← Wróć do logowania'}
          </button>
        </div>
      </div>
    </div>
  );
}
