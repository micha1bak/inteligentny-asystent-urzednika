import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMagazyn } from '../magazyn';
import { STATUSY, type Status, type Wniosek } from '../types';
import { dzisIso, formatuj } from '../lib/daty';
import { maksDniKwerendy, OPIS_PILNOSCI, pilnosc } from '../lib/terminy';
import { Pozostalo, ZnaczekStatusu } from '../components/Znaczki';
import { PodobneSprawy, ProponowaneWydzialy } from '../components/Podpowiedzi';
import StrefaPliku from '../components/StrefaPliku';
import EdytorAnonimizacji from '../components/EdytorAnonimizacji';
import { ETAPY_OCENY, JEDNOSTKI, SLOWNIK_WERDYKTOW, jednostka } from '../dane/referencje';
import { brakujacePola, generujProjekt } from '../lib/pismo';
import { wykryj, zastosuj } from '../lib/anonimizacja';
import { eksportujDocx, eksportujTxt } from '../lib/eksport';

export default function Sprawa() {
  const { id } = useParams();
  const { wnioski, aktualizujWniosek, usunWniosek } = useMagazyn();
  const nav = useNavigate();
  const w = wnioski.find((x) => x.id === id);
  if (!w) {
    return (
      <div className="karta">
        Nie znaleziono wniosku. <Link to="/">Wróć do kalendarza</Link>
      </div>
    );
  }
  const zmien = (z: Partial<Wniosek>) => aktualizujWniosek(w.id, z);
  const p = pilnosc(w, dzisIso());

  return (
    <>
      <Link to="/" className="maly">← Kalendarz wniosków</Link>
      <div className="rzad rozsun" style={{ margin: '8px 0 4px' }}>
        <div>
          <div className="numer maly">{w.numer}</div>
          <h1>{w.temat}</h1>
          <div className="rzad maly">
            <span>Wpływ: {formatuj(w.dataWplywu)}</span>·
            <span>Termin: <strong>{formatuj(p.termin)}</strong></span>·
            <Pozostalo pilnosc={p.pilnosc} pozostalo={p.pozostalo} />
            {p.pilnosc !== 'zakonczony' && p.pilnosc !== 'w_terminie' && <span className={`znaczek pil-${p.pilnosc}`}>{OPIS_PILNOSCI[p.pilnosc]}</span>}
            · <span>Prowadzi: {w.inicjaly || '—'}</span>
          </div>
        </div>
        <ZnaczekStatusu status={w.status} dniKwerendy={w.dniKwerendy} />
      </div>

      <Statusy w={w} zmien={zmien} />

      <div className="siatka-2" style={{ marginTop: 18 }}>
        <div className="stos">
          <TrescWniosku w={w} zmien={zmien} />
          <OdpowiedziWydzialow w={w} zmien={zmien} />
          <ProjektPisma w={w} zmien={zmien} />
        </div>
        <div className="stos">
          <ProponowaneWydzialy
            tekst={`${w.temat} ${w.tresc}`}
            wybrane={w.wydzialy}
            onZmien={(wydzialy) =>
              zmien({ wydzialy, status: w.status === 'brak_dzialan' && wydzialy.length ? 'zapytania_wyslane' : w.status })
            }
          />
          <PodobneSprawy tekst={`${w.temat} ${w.tresc}`} pomijajId={w.id} />
          <OcenaPrawna w={w} zmien={zmien} />
          <div className="rzad">
            <button
              className="maly-p"
              onClick={() => {
                if (confirm(`Usunąć wniosek ${w.numer}? Tej operacji nie można cofnąć.`)) {
                  usunWniosek(w.id);
                  nav('/');
                }
              }}
            >
              Usuń wniosek
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

type Props = { w: Wniosek; zmien: (z: Partial<Wniosek>) => void };

function Statusy({ w, zmien }: Props) {
  const [kwerendaOtwarta, setKwerendaOtwarta] = useState(false);
  const [dni, setDni] = useState(w.dniKwerendy ?? 14);
  const [dataWysylki, setDataWysylki] = useState(w.dataOdpowiedzi ?? dzisIso());
  const [wysylkaOtwarta, setWysylkaOtwarta] = useState(false);
  const indeks = STATUSY.findIndex((s) => s.id === w.status);
  const maks = maksDniKwerendy(w.dataWplywu);

  function ustaw(s: Status) {
    setKwerendaOtwarta(s === 'kwerenda');
    setWysylkaOtwarta(s === 'odpowiedz_wyslana');
    if (s === 'kwerenda' || s === 'odpowiedz_wyslana') return;
    zmien({ status: s, dataOdpowiedzi: undefined });
  }

  return (
    <div className="karta">
      <div className="krokownik">
        {STATUSY.map((s, i) => (
          <button key={s.id} className={`krok ${i < indeks ? 'zrobiony' : ''} ${i === indeks ? 'biezacy zrobiony' : ''}`} onClick={() => ustaw(s.id)}>
            {s.etykieta}
          </button>
        ))}
      </div>
      {kwerendaOtwarta && (
        <div className="rzad" style={{ marginTop: 10 }}>
          <label style={{ flexDirection: 'row', alignItems: 'center' }}>
            Dodatkowe dni na odpowiedź
            <input type="number" min={1} max={maks} value={dni} onChange={(e) => setDni(Math.max(1, Math.min(maks, Number(e.target.value))))} style={{ width: 80 }} />
          </label>
          <button className="glowny maly-p" onClick={() => { zmien({ status: 'kwerenda', dniKwerendy: dni }); setKwerendaOtwarta(false); }}>Zapisz kwerendę</button>
          <span className="maly">Maks. {maks} dni (2 miesiące od wpływu). Pamiętaj o powiadomieniu wnioskodawcy o przyczynach i nowym terminie (art. 13 ust. 2 UDIP).</span>
        </div>
      )}
      {wysylkaOtwarta && (
        <div className="rzad" style={{ marginTop: 10 }}>
          <label style={{ flexDirection: 'row', alignItems: 'center' }}>
            Data wysłania odpowiedzi
            <input type="date" value={dataWysylki} onChange={(e) => setDataWysylki(e.target.value)} style={{ width: 160 }} />
          </label>
          <button className="glowny maly-p" onClick={() => { zmien({ status: 'odpowiedz_wyslana', dataOdpowiedzi: dataWysylki }); setWysylkaOtwarta(false); }}>Oznacz jako wysłaną</button>
          <span className="maly">Program nie wysyła odpowiedzi – tylko odnotowuje, że wysłałeś ją sam.</span>
        </div>
      )}
    </div>
  );
}

function TrescWniosku({ w, zmien }: Props) {
  const [edycja, setEdycja] = useState(false);
  return (
    <div className="karta">
      <div className="rzad rozsun">
        <h2>Wniosek</h2>
        <button className="maly-p" onClick={() => setEdycja(!edycja)}>{edycja ? 'Zakończ edycję' : 'Edytuj dane'}</button>
      </div>
      {edycja ? (
        <div className="formularz">
          <label>Nr wniosku<input value={w.numer} onChange={(e) => zmien({ numer: e.target.value })} /></label>
          <label>Data wpływu<input type="date" value={w.dataWplywu} onChange={(e) => e.target.value && zmien({ dataWplywu: e.target.value })} /></label>
          <label>Wnioskodawca<input value={w.wnioskodawca} onChange={(e) => zmien({ wnioskodawca: e.target.value })} /></label>
          <label>Adres do odpowiedzi<input value={w.kontakt ?? ''} onChange={(e) => zmien({ kontakt: e.target.value })} /></label>
          <label className="pelny">Temat<input value={w.temat} onChange={(e) => zmien({ temat: e.target.value })} /></label>
          <label>Inicjały<input value={w.inicjaly} maxLength={4} onChange={(e) => zmien({ inicjaly: e.target.value.toUpperCase() })} /></label>
          <label className="pelny">Treść<textarea rows={8} value={w.tresc} onChange={(e) => zmien({ tresc: e.target.value })} /></label>
        </div>
      ) : (
        <>
          <dl className="dane-kv" style={{ marginBottom: 12 }}>
            <dt>Wnioskodawca</dt><dd>{w.wnioskodawca || '—'}</dd>
            <dt>Adres do odpowiedzi</dt><dd>{w.kontakt || '—'}</dd>
            {w.nazwaPliku && (<><dt>Plik</dt><dd>{w.nazwaPliku}</dd></>)}
          </dl>
          <div className="pole-tekstu">{w.tresc}</div>
        </>
      )}
    </div>
  );
}

function OdpowiedziWydzialow({ w, zmien }: Props) {
  const [wydzial, setWydzial] = useState(w.wydzialy[0] ?? '');
  const [wklej, setWklej] = useState('');
  const dodaj = (tresc: string, nazwaPliku?: string) =>
    zmien({
      odpowiedzi: [...w.odpowiedzi, { id: crypto.randomUUID(), wydzial: wydzial || '—', tresc, nazwaPliku, dodano: dzisIso() }],
    });

  return (
    <div className="karta">
      <h2>Odpowiedzi wydziałów</h2>
      {w.odpowiedzi.length > 0 && (
        <ul className="lista" style={{ marginBottom: 14 }}>
          {w.odpowiedzi.map((o) => (
            <li key={o.id}>
              <div className="rzad rozsun">
                <strong>{o.wydzial} {jednostka(o.wydzial) ? `– ${jednostka(o.wydzial)!.nazwa}` : ''}</strong>
                <button className="maly-p" onClick={() => zmien({ odpowiedzi: w.odpowiedzi.filter((x) => x.id !== o.id) })}>Usuń</button>
              </div>
              <div className="maly">{formatuj(o.dodano)}{o.nazwaPliku ? ` · ${o.nazwaPliku}` : ''}</div>
              <p style={{ margin: '6px 0 0', fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{o.tresc}</p>
            </li>
          ))}
        </ul>
      )}
      <div className="rzad" style={{ marginBottom: 8 }}>
        <label style={{ flex: 1 }}>
          Od kogo
          <select value={wydzial} onChange={(e) => setWydzial(e.target.value)}>
            <option value="">— wybierz jednostkę —</option>
            {[...w.wydzialy, ...JEDNOSTKI.map((j) => j.symbol).filter((s) => !w.wydzialy.includes(s))].map((s) => (
              <option key={s} value={s}>{s} – {jednostka(s)?.nazwa}</option>
            ))}
          </select>
        </label>
      </div>
      <StrefaPliku napis="Wgraj odpowiedź wydziału" wielokrotny onWczytano={(t, f) => dodaj(t, f.name)} />
      <details style={{ marginTop: 10 }}>
        <summary className="maly">…albo wklej treść odpowiedzi</summary>
        <textarea rows={4} value={wklej} onChange={(e) => setWklej(e.target.value)} style={{ marginTop: 6 }} />
        <button className="maly-p" style={{ marginTop: 6 }} disabled={!wklej.trim()} onClick={() => { dodaj(wklej.trim()); setWklej(''); }}>Dodaj odpowiedź</button>
      </details>
    </div>
  );
}

function ProjektPisma({ w, zmien }: Props) {
  const tekst = w.projektPisma;
  const fragmenty = w.fragmenty ?? [];

  function generuj() {
    if (tekst && !confirm('Wygenerować projekt od nowa? Twoje poprawki w obecnym projekcie zostaną zastąpione.')) return;
    const nowy = generujProjekt(w, dzisIso());
    zmien({ projektPisma: nowy, fragmenty: wykryj(nowy) });
  }

  const doDecyzji = fragmenty.filter((f) => f.stan === 'propozycja').length;
  const brakuje = tekst ? brakujacePola(tekst) : [];
  const wynik = tekst ? zastosuj(tekst, fragmenty) : '';

  return (
    <div className="karta">
      <div className="rzad rozsun">
        <h2>Projekt odpowiedzi</h2>
        <button className={tekst ? 'maly-p' : 'glowny'} onClick={generuj}>{tekst ? 'Generuj ponownie' : 'Przygotuj projekt pisma'}</button>
      </div>
      {!tekst ? (
        <p className="maly">
          Projekt powstanie z danych wniosku i wgranych odpowiedzi wydziałów ({w.odpowiedzi.length}). Dane osobowe zostaną zaznaczone do anonimizacji.
        </p>
      ) : (
        <>
          <EdytorAnonimizacji tekst={tekst} fragmenty={fragmenty} onZmien={(t, f) => zmien({ projektPisma: t, fragmenty: f })} />
          {(brakuje.length > 0 || doDecyzji > 0) && (
            <div className="uwaga" style={{ marginTop: 10 }}>
              {brakuje.length > 0 && <div>Do uzupełnienia: {brakuje.join('; ')}</div>}
              {doDecyzji > 0 && <div>Nierozpatrzone propozycje anonimizacji: {doDecyzji}</div>}
            </div>
          )}
          <div className="rzad" style={{ marginTop: 12 }}>
            <button className="glowny" onClick={() => void eksportujDocx(wynik, w.numer)}>Pobierz DOCX</button>
            <button onClick={() => eksportujTxt(wynik, w.numer)}>Pobierz TXT</button>
            {w.status !== 'odpowiedz_przygotowana' && w.status !== 'odpowiedz_wyslana' && (
              <button onClick={() => zmien({ status: 'odpowiedz_przygotowana' })}>Oznacz: odpowiedź przygotowana</button>
            )}
          </div>
          <p className="maly" style={{ marginBottom: 0 }}>Plik zawiera wersję po anonimizacji. Sprawdź merytorycznie treść przed wysłaniem – to projekt, nie gotowe pismo.</p>
        </>
      )}
    </div>
  );
}

function OcenaPrawna({ w, zmien }: Props) {
  const etapy = w.ocenaEtapy ?? {};
  const zrobione = ETAPY_OCENY.filter((e) => etapy[e.id]).length;
  return (
    <div className="karta">
      <h2>Ocena prawna</h2>
      <label>
        Rozstrzygnięcie
        <select value={w.werdykt ?? ''} onChange={(e) => zmien({ werdykt: e.target.value || undefined })}>
          <option value="">— nie wybrano —</option>
          {Object.keys(SLOWNIK_WERDYKTOW).map((k) => <option key={k} value={k}>{k.replaceAll('_', ' ').toLowerCase()}</option>)}
        </select>
      </label>
      {w.werdykt && <p className="maly">{SLOWNIK_WERDYKTOW[w.werdykt]}</p>}
      <details style={{ marginTop: 10 }}>
        <summary>Lista kontrolna ({zrobione}/{ETAPY_OCENY.length} etapów)</summary>
        <ul className="lista" style={{ marginTop: 8 }}>
          {ETAPY_OCENY.map((e) => (
            <li key={e.id}>
              <label style={{ flexDirection: 'row', gap: 8, color: 'inherit', alignItems: 'flex-start' }}>
                <input type="checkbox" style={{ width: 'auto', marginTop: 3 }} checked={!!etapy[e.id]} onChange={(ev) => zmien({ ocenaEtapy: { ...etapy, [e.id]: ev.target.checked } })} />
                <span>
                  <strong style={{ fontSize: '0.88rem' }}>{e.nazwa}</strong>
                  <span className="maly" style={{ display: 'block' }}>{e.informacja}</span>
                  <details>
                    <summary className="maly">Założenia i podstawy</summary>
                    <ul style={{ fontSize: '0.82rem', paddingLeft: 18 }}>
                      {e.zalozenia.map((z, i) => <li key={i} style={{ border: 0, padding: '2px 0' }}>{z}</li>)}
                    </ul>
                  </details>
                </span>
              </label>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
