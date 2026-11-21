import { useCallback, useEffect, useRef, useState } from 'react';
import RoznicaWartosci from '../components/RoznicaWartosci';
import {
  pobierzAnalize,
  pobierzStanBazyWiedzy,
  ROZSZERZENIA_AKTU,
  wgrajAkt,
  wycofajWersje,
  zastosujAnalize,
  type AnalizaAktu,
  type ProponowanaZmiana,
  type StanBazyWiedzy,
} from '../lib/api';
import { dzisIso, formatuj } from '../lib/daty';
import { zapamietaneInicjaly, zapamietajInicjaly } from '../lib/inicjaly';

const KLUCZ_ANALIZY = 'asystent.analiza-aktu';
const STATUSY_WERSJI: Record<string, string> = {
  obowiazuje: 'obowiązuje',
  zaplanowana: 'zaplanowana',
  archiwalna: 'archiwalna',
  wycofana: 'wycofana',
};

function zapamietajAnalize(id: string | null) {
  try {
    if (id) sessionStorage.setItem(KLUCZ_ANALIZY, id);
    else sessionStorage.removeItem(KLUCZ_ANALIZY);
  } catch {
    /* bez znaczenia */
  }
}

function zapamietanaAnaliza(): string | null {
  try {
    return sessionStorage.getItem(KLUCZ_ANALIZY);
  } catch {
    return null;
  }
}

const komunikat = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function BazaWiedzy() {
  const [stan, setStan] = useState<StanBazyWiedzy>();
  const [blad, setBlad] = useState('');
  const [analiza, setAnaliza] = useState<AnalizaAktu>();
  const [autor, setAutor] = useState(zapamietaneInicjaly);

  const odswiez = useCallback(() => {
    pobierzStanBazyWiedzy()
      .then(setStan)
      .catch((e) => setBlad(komunikat(e)));
  }, []);

  useEffect(() => {
    odswiez();
    const id = zapamietanaAnaliza(); // powrót na stronę w trakcie analizy
    if (id) pobierzAnalize(id).then(setAnaliza).catch(() => zapamietajAnalize(null));
  }, [odswiez]);

  // odpytywanie o postęp analizy działającej w tle
  useEffect(() => {
    if (analiza?.status !== 'w_toku') return;
    const t = setTimeout(() => {
      pobierzAnalize(analiza.id)
        .then(setAnaliza)
        .catch((e) => setBlad(komunikat(e)));
    }, 2000);
    return () => clearTimeout(t);
  }, [analiza]);

  function ustawAutora(v: string) {
    setAutor(v.toUpperCase());
    zapamietajInicjaly(v.toUpperCase());
  }

  return (
    <>
      <div className="rzad rozsun" style={{ alignItems: 'flex-start' }}>
        <div>
          <h1>Baza wiedzy prawnej</h1>
          <p className="podtytul">
            Po zmianie przepisów wgraj nowy tekst aktu – model wskaże, które fragmenty algorytmu oceny trzeba zaktualizować.
            Nic nie zmienia się bez Twojej akceptacji, a każdą wersję można wycofać.
          </p>
        </div>
        <label style={{ width: 120 }}>
          Twoje inicjały
          <input value={autor} maxLength={4} onChange={(e) => ustawAutora(e.target.value)} />
        </label>
      </div>
      {blad && <div className="blad" style={{ marginBottom: 12 }}>{blad}</div>}

      <div className="stos">
        {!analiza || analiza.status === 'zapisana' ? (
          <>
            {analiza?.status === 'zapisana' && (
              <div className="info">
                Zapisano wersję bazy wiedzy {analiza.zapisana_wersja} ({analiza.akt.skrot}), obowiązuje od {formatuj(analiza.akt.obowiazuje_od)}.
              </div>
            )}
            <FormularzAktu
              stan={stan}
              onStart={(a) => {
                setAnaliza(a);
                zapamietajAnalize(a.id);
              }}
            />
          </>
        ) : (
          <WynikAnalizy
            analiza={analiza}
            autor={autor}
            onZapisano={(a) => {
              setAnaliza(a);
              zapamietajAnalize(null);
              odswiez();
            }}
            onAnuluj={() => {
              setAnaliza(undefined);
              zapamietajAnalize(null);
            }}
          />
        )}
        <HistoriaWersji stan={stan} autor={autor} onZmiana={odswiez} />
      </div>
    </>
  );
}

function FormularzAktu({ stan, onStart }: { stan?: StanBazyWiedzy; onStart: (a: AnalizaAktu) => void }) {
  const [plik, setPlik] = useState<File>();
  const [zastepuje, setZastepuje] = useState<string>();
  const [nazwa, setNazwa] = useState('');
  const [skrot, setSkrot] = useState('');
  const [publikator, setPublikator] = useState('');
  const [obowiazujeOd, setObowiazujeOd] = useState(dzisIso());
  const [blad, setBlad] = useState('');
  const [trwa, setTrwa] = useState(false);
  const wejscie = useRef<HTMLInputElement>(null);

  const wybor = zastepuje ?? stan?.akty[0]?.plik ?? '';
  const nowy = wybor === '';
  const gotowe = !!plik && !!obowiazujeOd && (!nowy || (nazwa.trim() && skrot.trim()));

  async function wyslij() {
    if (!plik) return;
    setTrwa(true);
    setBlad('');
    try {
      onStart(await wgrajAkt({ plik, zastepuje: wybor, nazwa, skrot, publikator, obowiazujeOd }));
    } catch (e) {
      setBlad(komunikat(e));
    } finally {
      setTrwa(false);
    }
  }

  return (
    <div className="karta">
      <h2>Wgraj akt prawny</h2>
      <div className="formularz">
        <label className="pelny">
          Co wgrywasz
          <select value={wybor} onChange={(e) => setZastepuje(e.target.value)}>
            {stan?.akty.map((a) => (
              <option key={a.plik} value={a.plik}>
                Nową wersję (np. tekst jednolity, nowelizację): {a.nazwa}
              </option>
            ))}
            <option value="">Nowy akt prawny</option>
          </select>
          {!nowy && <span>Obecny plik: {wybor} – zostanie porównany z nową wersją artykuł po artykule.</span>}
        </label>
        <label className="pelny">
          Plik aktu (PDF z warstwą tekstową, DOCX lub TXT)
          <div className="rzad">
            <button type="button" onClick={() => wejscie.current?.click()}>{plik ? 'Zmień plik' : 'Wybierz plik'}</button>
            <span className="maly">{plik ? plik.name : 'nie wybrano pliku'}</span>
          </div>
          <input
            ref={wejscie}
            type="file"
            hidden
            accept={ROZSZERZENIA_AKTU.join(',')}
            onChange={(e) => {
              setPlik(e.target.files?.[0]);
              e.target.value = '';
            }}
          />
        </label>
        <label className="pelny">
          Pełna nazwa aktu {nowy ? '' : '(zostaw puste, jeśli się nie zmienia)'}
          <input value={nazwa} onChange={(e) => setNazwa(e.target.value)} placeholder="np. Ustawa z dnia 6 września 2001 r. o dostępie do informacji publicznej" />
        </label>
        {nowy && (
          <label>
            Skrót
            <input value={skrot} maxLength={40} onChange={(e) => setSkrot(e.target.value)} placeholder="np. UODO" />
          </label>
        )}
        <label>
          Data wejścia w życie
          <input type="date" value={obowiazujeOd} onChange={(e) => setObowiazujeOd(e.target.value)} />
          {obowiazujeOd > dzisIso() && <span>Zmiany zaczną obowiązywać od tego dnia – do tego czasu wnioski są oceniane po staremu.</span>}
        </label>
        <label className={nowy ? '' : 'pelny'}>
          Publikator
          <input value={publikator} onChange={(e) => setPublikator(e.target.value)} placeholder="np. t.j. Dz. U. z 2026 r. poz. 123" />
        </label>
      </div>
      <div className="uwaga" style={{ marginTop: 12 }}>
        Zmienione przepisy i fragmenty bazy wiedzy są wysyłane do modelu (Groq). Nie wgrywaj zarządzeń wewnętrznych, które nie mogą
        opuścić urzędu. Analiza trwa od kilkunastu sekund do kilku minut (limit zapytań darmowego planu).
      </div>
      {blad && <div className="blad" style={{ marginTop: 12 }}>{blad}</div>}
      <div className="rzad" style={{ marginTop: 14 }}>
        <button className="glowny" disabled={!gotowe || trwa} onClick={wyslij}>
          {trwa ? 'Wysyłam…' : 'Analizuj akt'}
        </button>
        {!gotowe && <span className="maly">Wybierz plik{nowy ? ', podaj nazwę i skrót aktu' : ''}.</span>}
      </div>
    </div>
  );
}

type Decyzja = { zatwierdz: boolean; po?: unknown };

function WynikAnalizy({
  analiza,
  autor,
  onZapisano,
  onAnuluj,
}: {
  analiza: AnalizaAktu;
  autor: string;
  onZapisano: (a: AnalizaAktu) => void;
  onAnuluj: () => void;
}) {
  const [decyzje, setDecyzje] = useState<Record<string, Decyzja>>({});
  const [blad, setBlad] = useState('');
  const [trwa, setTrwa] = useState(false);
  const { status, postep, akt } = analiza;
  const brakDecyzji = analiza.zmiany.filter((z) => !decyzje[z.id]).length;

  async function zapisz() {
    if (!autor.trim()) {
      setBlad('Wpisz swoje inicjały (u góry strony) – trafią do historii wersji.');
      return;
    }
    setTrwa(true);
    setBlad('');
    try {
      const lista = analiza.zmiany.map((z) => ({ id: z.id, ...decyzje[z.id] }));
      const wersja = await zastosujAnalize(analiza.id, lista, autor.trim());
      onZapisano({ ...analiza, status: 'zapisana', zapisana_wersja: wersja.id });
    } catch (e) {
      setBlad(komunikat(e));
    } finally {
      setTrwa(false);
    }
  }

  return (
    <div className="karta">
      <div className="rzad rozsun" style={{ marginBottom: 10 }}>
        <h2 style={{ margin: 0 }}>
          Analiza: {akt.skrot} {akt.nowy ? '(nowy akt)' : '(nowa wersja)'}
        </h2>
        <button className="maly-p" onClick={onAnuluj} disabled={trwa}>
          {status === 'w_toku' ? 'Ukryj (analiza trwa dalej)' : 'Zamknij bez zapisu'}
        </button>
      </div>
      <p className="maly" style={{ marginTop: 0 }}>
        {akt.nazwa || akt.nazwa_pliku} · obowiązuje od {formatuj(akt.obowiazuje_od)}
        {akt.publikator ? ` · ${akt.publikator}` : ''}
      </p>

      {status === 'w_toku' && (
        <>
          <strong>{postep.opis || 'Analizuję'}…</strong>
          {postep.wszystkie > 1 ? (
            <div className="postep" role="progressbar" aria-valuenow={Math.round((100 * postep.zrobione) / postep.wszystkie)}>
              <div style={{ width: `${Math.round((100 * postep.zrobione) / postep.wszystkie)}%` }} />
            </div>
          ) : (
            <div className="postep postep-ciagly" role="progressbar"><div /></div>
          )}
          <p className="maly">Możesz przejść do innej zakładki – analiza trwa w tle, a wynik pojawi się po powrocie.</p>
        </>
      )}
      {status === 'nie_dotyczy' && <div className="info">{analiza.komunikat}</div>}
      {status === 'blad' && <div className="blad">{analiza.komunikat}</div>}

      {analiza.ostrzezenia.length > 0 && (
        <div className="uwaga" style={{ margin: '12px 0' }}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {analiza.ostrzezenia.map((o) => <li key={o}>{o}</li>)}
          </ul>
        </div>
      )}

      {analiza.roznice.length > 0 && (
        <>
          <h3 style={{ marginTop: 16 }}>Zmienione przepisy ({analiza.roznice.length})</h3>
          {analiza.roznice.map((r) => (
            <details key={r.etykieta} className="przepis-zmiana">
              <summary>
                <strong>{r.etykieta}</strong> <span className={`znaczek r-${r.rodzaj}`}>{r.rodzaj}</span>
              </summary>
              <div className="roznica-kolumny">
                <div className="roznica-przed"><div className="maly">Dotychczas</div><div className="tekst-przepisu">{r.przed || '—'}</div></div>
                <div className="roznica-po"><div className="maly">Obecnie</div><div className="tekst-przepisu">{r.po || '—'}</div></div>
              </div>
            </details>
          ))}
        </>
      )}

      {(status === 'gotowa' || (status === 'w_toku' && analiza.zmiany.length > 0)) && (
        <>
          <h3 style={{ marginTop: 16 }}>Proponowane zmiany w bazie wiedzy ({analiza.zmiany.length})</h3>
          {analiza.zmiany.length === 0 && <p className="maly">Brak zmian w bazie wiedzy. Możesz zapisać wersję, żeby zaktualizować tekst aktu.</p>}
          {analiza.zmiany.map((z) => (
            <KartaZmiany
              key={z.id}
              zmiana={z}
              decyzja={decyzje[z.id]}
              aktywna={status === 'gotowa'}
              onDecyzja={(d) => setDecyzje((s) => ({ ...s, [z.id]: d }))}
            />
          ))}
        </>
      )}

      {status === 'gotowa' && (
        <>
          {blad && <div className="blad" style={{ marginTop: 12 }}>{blad}</div>}
          <div className="rzad" style={{ marginTop: 14 }}>
            <button className="glowny" disabled={trwa || brakDecyzji > 0} onClick={zapisz}>
              Zapisz nową wersję bazy wiedzy
            </button>
            {brakDecyzji > 0 ? (
              <span className="maly">Zatwierdź albo odrzuć każdą zmianę (zostało: {brakDecyzji}).</span>
            ) : (
              <span className="maly">
                Zapisane zostaną zatwierdzone zmiany i nowy tekst aktu (wyszukiwarka przepisów); obowiązują od {formatuj(akt.obowiazuje_od)}.
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function KartaZmiany({
  zmiana,
  decyzja,
  aktywna,
  onDecyzja,
}: {
  zmiana: ProponowanaZmiana;
  decyzja?: Decyzja;
  aktywna: boolean;
  onDecyzja: (d: Decyzja) => void;
}) {
  const [edycja, setEdycja] = useState<string | null>(null);
  const [bladJson, setBladJson] = useState('');
  const po = decyzja?.po ?? zmiana.po;

  function zastosujPoprawke() {
    try {
      const wartosc = JSON.parse(edycja ?? '');
      onDecyzja({ zatwierdz: true, po: wartosc });
      setEdycja(null);
      setBladJson('');
    } catch {
      setBladJson('To nie jest poprawny JSON – sprawdź nawiasy i cudzysłowy.');
    }
  }

  const stanDecyzji = !decyzja ? '' : !decyzja.zatwierdz ? 'odrzucona' : decyzja.po !== undefined ? 'poprawiona' : 'zatwierdzona';

  return (
    <div className={`karta-zmiany ${stanDecyzji ? `d-${stanDecyzji}` : ''}`}>
      <div className="rzad rozsun">
        <div>
          <strong>{zmiana.opis}</strong>
          <div className="maly numer">{zmiana.klucz}</div>
        </div>
        <div className="rzad" style={{ gap: 6 }}>
          {zmiana.zrodlo === 'metadane' && <span className="znaczek w-inne">dane aktu</span>}
          {stanDecyzji && <span className={`znaczek d-${stanDecyzji}`}>{stanDecyzji}</span>}
        </div>
      </div>
      {zmiana.uzasadnienie && <p style={{ margin: '8px 0' }}>{zmiana.uzasadnienie}</p>}
      {zmiana.przepisy.length > 0 && <p className="maly" style={{ margin: '0 0 8px' }}>Przepisy: {zmiana.przepisy.join('; ')}</p>}

      {edycja === null ? (
        <RoznicaWartosci przed={zmiana.przed} po={po} />
      ) : (
        <>
          <textarea rows={14} className="json" value={edycja} onChange={(e) => setEdycja(e.target.value)} spellCheck={false} />
          {bladJson && <div className="blad" style={{ marginTop: 6 }}>{bladJson}</div>}
        </>
      )}

      {aktywna && (
        <div className="rzad" style={{ marginTop: 10 }}>
          {edycja === null ? (
            <>
              <button className="maly-p" onClick={() => onDecyzja({ zatwierdz: true })}>Zatwierdź</button>
              <button className="maly-p" onClick={() => onDecyzja({ zatwierdz: false })}>Odrzuć</button>
              <button className="maly-p" onClick={() => setEdycja(JSON.stringify(po, null, 2))}>Popraw</button>
            </>
          ) : (
            <>
              <button className="maly-p" onClick={zastosujPoprawke}>Zatwierdź z poprawką</button>
              <button className="maly-p" onClick={() => { setEdycja(null); setBladJson(''); }}>Anuluj</button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function HistoriaWersji({ stan, autor, onZmiana }: { stan?: StanBazyWiedzy; autor: string; onZmiana: () => void }) {
  const [blad, setBlad] = useState('');

  async function wycofaj(id: string) {
    if (!autor.trim()) {
      setBlad('Wpisz swoje inicjały (u góry strony) – trafią do historii wersji.');
      return;
    }
    if (!confirm(`Wycofać wersję ${id}? Baza wiedzy i tekst aktu wrócą do poprzedniej wersji.`)) return;
    setBlad('');
    try {
      await wycofajWersje(id, autor.trim());
      onZmiana();
    } catch (e) {
      setBlad(komunikat(e));
    }
  }

  return (
    <div className="karta">
      <h2>Historia wersji</h2>
      {blad && <div className="blad" style={{ marginBottom: 10 }}>{blad}</div>}
      {!stan ? (
        <p className="maly">Wczytuję…</p>
      ) : stan.wersje.length === 0 ? (
        <p className="maly">Baza wiedzy nie była jeszcze aktualizowana z aplikacji – obowiązuje wersja początkowa.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Wersja</th>
                <th>Opis</th>
                <th>Obowiązuje od</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {stan.wersje.map((w) => (
                <tr key={w.id} className={w.status === 'wycofana' ? 'nieaktualny' : ''}>
                  <td className="numer">{w.id}</td>
                  <td>
                    {w.opis}
                    <div className="maly">
                      {w.autor} · {new Date(w.utworzono).toLocaleString('pl-PL')}
                      {w.wycofana ? ` · wycofał(a) ${w.wycofana.kto} ${new Date(w.wycofana.kiedy).toLocaleString('pl-PL')}` : ''}
                    </div>
                    {w.zmiany.length > 0 && (
                      <details>
                        <summary className="maly">Zmienione elementy ({w.zmiany.length})</summary>
                        <ul className="lista-zwarta maly">
                          {w.zmiany.map((z) => <li key={z.klucz}>{z.opis}</li>)}
                        </ul>
                      </details>
                    )}
                  </td>
                  <td className="nowrap">{w.obowiazuje_od ? formatuj(w.obowiazuje_od) : '—'}</td>
                  <td><span className={`znaczek v-${w.status}`}>{STATUSY_WERSJI[w.status]}</span></td>
                  <td>
                    {w.id !== 'v0' && w.status !== 'wycofana' && (
                      <button className="maly-p" onClick={() => wycofaj(w.id)}>Wycofaj</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
