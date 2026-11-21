import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import FormularzSprawy, { brakujacePola } from '../components/FormularzSprawy';
import { pobierzArchiwum, usunZArchiwum, zmienWArchiwum, type Archiwum as DaneArchiwum, type Sprawa, type SprawaZArchiwum } from '../lib/api';
import { formatuj } from '../lib/daty';
import { zapamietaneInicjaly, zapamietajInicjaly } from '../lib/inicjaly';

export function ZnaczekWerdyktu({ werdykt, opis }: { werdykt: string; opis?: string }) {
  const rodzaj = werdykt.startsWith('MOZNA') ? 'w-mozna' : werdykt.startsWith('NIE') ? 'w-nie' : 'w-inne';
  return <span className={`znaczek ${rodzaj}`} title={opis}>{werdykt}</span>;
}

const NAZWY_POL: Record<string, string> = {
  data_odpowiedzi: 'data odpowiedzi',
  komorka_merytoryczna: 'komórka',
  wniosek_o_co: 'wniosek',
  jaka_odpowiedz: 'odpowiedź',
  werdykt: 'werdykt',
  forma_zalatwienia: 'forma załatwienia',
  etap_i_podstawa: 'podstawa prawna',
};

function skrot(tekst: string, dlugosc: number): string {
  return tekst.length <= dlugosc ? tekst : tekst.slice(0, dlugosc).replace(/\s+\S*$/, '') + '…';
}

function pasuje(s: SprawaZArchiwum, fraza: string): boolean {
  if (!fraza) return true;
  const f = fraza.toLowerCase();
  return [s.sygnatura, s.wniosek_o_co, s.jaka_odpowiedz, s.komorka_merytoryczna, s.werdykt].some((t) => t.toLowerCase().includes(f));
}

export default function Archiwum() {
  const [dane, setDane] = useState<DaneArchiwum>();
  const [blad, setBlad] = useState('');
  const [fraza, setFraza] = useState('');
  const [nieaktualne, setNieaktualne] = useState(false);
  const [wybrana, setWybrana] = useState<string>();

  useEffect(() => {
    const ac = new AbortController();
    pobierzArchiwum(ac.signal)
      .then(setDane)
      .catch((e) => !(e instanceof DOMException && e.name === 'AbortError') && setBlad(e instanceof Error ? e.message : String(e)));
    return () => ac.abort();
  }, []);

  const widoczne = useMemo(
    () => (dane?.sprawy ?? []).filter((s) => (nieaktualne || !s.nieaktualna) && pasuje(s, fraza)),
    [dane, fraza, nieaktualne],
  );
  const sprawa = dane?.sprawy.find((s) => s.sygnatura === wybrana);
  const liczbaNieaktualnych = dane?.sprawy.filter((s) => s.nieaktualna).length ?? 0;

  function podmien(nowa: SprawaZArchiwum) {
    setDane((d) => d && { ...d, sprawy: d.sprawy.map((s) => (s.sygnatura === nowa.sygnatura ? nowa : s)) });
  }

  function usunieto(sygnatura: string) {
    setDane((d) => d && { ...d, sprawy: d.sprawy.filter((s) => s.sygnatura !== sygnatura) });
    setWybrana(undefined);
  }

  return (
    <>
      <div className="rzad rozsun" style={{ marginBottom: 18 }}>
        <h1>Archiwum odpowiedzi</h1>
        <Link className="przycisk glowny" to="/archiwum/nowa">+ Dodaj sprawę</Link>
      </div>
      {blad && <div className="blad" style={{ marginBottom: 12 }}>{blad}</div>}

      <div className="siatka-2">
        <div className="karta">
          <div className="rzad" style={{ marginBottom: 12 }}>
            <input
              type="search"
              placeholder="Szukaj: sygnatura, temat, komórka, werdykt…"
              value={fraza}
              onChange={(e) => setFraza(e.target.value)}
              style={{ flex: 1, minWidth: 220, width: 'auto' }}
            />
            <label style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <input type="checkbox" style={{ width: 'auto' }} checked={nieaktualne} onChange={(e) => setNieaktualne(e.target.checked)} />
              Pokaż nieaktualne ({liczbaNieaktualnych})
            </label>
          </div>
          {!dane && !blad && <p className="maly">Wczytuję archiwum…</p>}
          {dane && (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Sprawa</th>
                    <th>Wniosek i werdykt</th>
                  </tr>
                </thead>
                <tbody>
                  {widoczne.map((s) => (
                    <tr
                      key={s.sygnatura}
                      className={`klikalny ${s.sygnatura === wybrana ? 'wybrany' : ''} ${s.nieaktualna ? 'nieaktualny' : ''}`}
                      onClick={() => setWybrana(s.sygnatura)}
                    >
                      <td className="nowrap">
                        <div className="numer">{s.sygnatura}</div>
                        <div className="maly">{formatuj(s.data_odpowiedzi) || '—'}</div>
                      </td>
                      <td>
                        <span className="temat-sprawy">{skrot(s.wniosek_o_co, 170)}</span>
                        <div className="rzad maly" style={{ marginTop: 4, gap: 6 }}>
                          <ZnaczekWerdyktu werdykt={s.werdykt} opis={dane.werdykty[s.werdykt]} />
                          {s.komorka_merytoryczna}
                          {s.nieaktualna ? ' · nieaktualna' : ''}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {widoczne.length === 0 && <p className="maly">Brak spraw spełniających kryteria.</p>}
            </div>
          )}
        </div>

        <div className="stos">
          {sprawa && dane ? (
            <Edycja key={sprawa.sygnatura} sprawa={sprawa} dane={dane} onZapisano={podmien} onUsunieto={usunieto} />
          ) : (
            <div className="karta"><p className="maly">Wybierz sprawę z listy.</p></div>
          )}
        </div>
      </div>
    </>
  );
}

function Edycja({
  sprawa,
  dane,
  onZapisano,
  onUsunieto,
}: {
  sprawa: SprawaZArchiwum;
  dane: DaneArchiwum;
  onZapisano: (s: SprawaZArchiwum) => void;
  onUsunieto: (sygnatura: string) => void;
}) {
  const { historia, ...poczatkowa } = sprawa;
  const [robocza, setRobocza] = useState<Sprawa>(poczatkowa);
  const [autor, setAutor] = useState(zapamietaneInicjaly);
  const [blad, setBlad] = useState('');
  const [info, setInfo] = useState('');
  const [trwa, setTrwa] = useState(false);

  const zmieniona = JSON.stringify(robocza) !== JSON.stringify(poczatkowa);
  const braki = brakujacePola(robocza);

  async function zapisz(s: Sprawa, komunikat: string) {
    if (!autor.trim()) {
      setBlad('Wpisz swoje inicjały – trafią do historii zmian.');
      return;
    }
    setTrwa(true);
    setBlad('');
    setInfo('');
    try {
      zapamietajInicjaly(autor.trim());
      const nowa = await zmienWArchiwum(s, autor.trim());
      onZapisano(nowa);
      const { historia: _, ...bez } = nowa;
      setRobocza(bez);
      setInfo(komunikat);
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    } finally {
      setTrwa(false);
    }
  }

  async function usun() {
    if (!confirm(`Usunąć sprawę ${sprawa.sygnatura} z archiwum? Tej operacji nie można cofnąć – zamiast tego możesz oznaczyć sprawę jako nieaktualną.`)) return;
    setTrwa(true);
    try {
      await usunZArchiwum(sprawa.sygnatura);
      onUsunieto(sprawa.sygnatura);
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
      setTrwa(false);
    }
  }

  return (
    <>
      <div className="karta">
        <div className="rzad rozsun" style={{ marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>Sprawa {sprawa.sygnatura}</h2>
          {sprawa.nieaktualna && <span className="znaczek w-inne">nieaktualna</span>}
        </div>
        {sprawa.nieaktualna && (
          <div className="uwaga" style={{ marginBottom: 12 }}>Sprawa jest oznaczona jako nieaktualna – model jej nie używa.</div>
        )}
        <FormularzSprawy sprawa={robocza} onZmiana={setRobocza} werdykty={dane.werdykty} jednostki={dane.jednostki} sygnaturaStala />
        <div className="rzad" style={{ marginTop: 14 }}>
          <label style={{ width: 110 }}>
            Twoje inicjały
            <input value={autor} maxLength={4} onChange={(e) => setAutor(e.target.value.toUpperCase())} />
          </label>
        </div>
        {blad && <div className="blad" style={{ marginTop: 12 }}>{blad}</div>}
        {info && <div className="info" style={{ marginTop: 12 }}>{info}</div>}
        <div className="rzad" style={{ marginTop: 14 }}>
          <button className="glowny" disabled={trwa || !zmieniona || braki.length > 0} onClick={() => zapisz(robocza, 'Zapisano zmiany.')}>
            Zapisz zmiany
          </button>
          <button
            disabled={trwa || zmieniona}
            title={zmieniona ? 'Najpierw zapisz albo cofnij zmiany w formularzu.' : undefined}
            onClick={() =>
              zapisz(
                { ...poczatkowa, nieaktualna: !sprawa.nieaktualna },
                sprawa.nieaktualna ? 'Sprawa znów jest używana przez model.' : 'Sprawa oznaczona jako nieaktualna – model nie będzie jej używał.',
              )
            }
          >
            {sprawa.nieaktualna ? 'Przywróć jako aktualną' : 'Oznacz jako nieaktualną'}
          </button>
          <button disabled={trwa} onClick={usun} style={{ color: 'var(--czerwony)' }}>Usuń</button>
        </div>
        {zmieniona && braki.length > 0 && <p className="maly">Uzupełnij: {braki.join(', ')}.</p>}
      </div>

      <div className="karta">
        <h2>Historia zmian</h2>
        {historia.length === 0 ? (
          <p className="maly">Brak zapisanych zmian – wpis pochodzi z pierwotnego archiwum.</p>
        ) : (
          <ul className="historia">
            {[...historia].reverse().map((h, i) => (
              <li key={i}>
                <strong>{h.zmiana}</strong> · {h.kto} · <span className="maly">{new Date(h.kiedy).toLocaleString('pl-PL')}</span>
                {Object.entries(h.pola).map(([pole, { przed, po }]) => (
                  <div key={pole} className="maly">
                    {NAZWY_POL[pole] ?? pole}: <s>{String(przed) || '—'}</s> → {String(po) || '—'}
                  </div>
                ))}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
