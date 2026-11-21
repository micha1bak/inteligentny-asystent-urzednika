import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import PropozycjaOdpowiedzi from '../components/PropozycjaOdpowiedzi';
import { Pozostalo, ZnaczekStatusu } from '../components/Znaczki';
import { pobierzWniosek } from '../lib/api';
import { dzisIso, formatuj } from '../lib/daty';
import { zapamietajInicjaly } from '../lib/inicjaly';
import { maksDniKwerendy, pilnosc, terminOdpowiedzi } from '../lib/terminy';
import { useMagazyn } from '../magazyn';
import { STATUSY, type Status, type Wniosek } from '../types';
import type { ZWniosku } from './NowaSprawaArchiwum';

export default function SzczegolyWniosku() {
  const { id } = useParams<{ id: string }>();
  const { wnioski, ladowanie, zmienWniosek, usunWniosek } = useMagazyn();
  const zMagazynu = wnioski.find((w) => w.id === id);
  const [pobrany, setPobrany] = useState<Wniosek | null>(null);
  const [bladPobrania, setBladPobrania] = useState('');
  const [trwaPobieranie, setTrwaPobieranie] = useState(false);

  useEffect(() => {
    if (!id || zMagazynu || ladowanie) return;
    const ac = new AbortController();
    setTrwaPobieranie(true);
    setBladPobrania('');
    pobierzWniosek(id, ac.signal)
      .then(setPobrany)
      .catch((e) => {
        if (!(e instanceof DOMException && e.name === 'AbortError')) {
          setBladPobrania(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => setTrwaPobieranie(false));
    return () => ac.abort();
  }, [id, zMagazynu, ladowanie]);

  const wniosek = zMagazynu ?? pobrany;

  if (ladowanie || trwaPobieranie) {
    return (
      <>
        <div className="rzad" style={{ marginBottom: 14 }}>
          <Link className="przycisk maly-p" to="/">← Wnioski</Link>
        </div>
        <div className="karta"><p className="maly">Wczytuję szczegóły wniosku…</p></div>
      </>
    );
  }

  if (!wniosek) {
    return (
      <>
        <div className="rzad" style={{ marginBottom: 14 }}>
          <Link className="przycisk maly-p" to="/">← Wnioski</Link>
        </div>
        <div className="karta">
          <p className="blad" style={{ margin: 0 }}>{bladPobrania || 'Nie znaleziono wniosku.'}</p>
        </div>
      </>
    );
  }

  return (
    <WidokSzczegolow
      key={wniosek.id}
      wniosek={wniosek}
      wszystkieWnioski={wnioski}
      onZapisz={(dane) => zmienWniosek(wniosek.id, dane)}
      onUsun={() => usunWniosek(wniosek.id)}
    />
  );
}

function WidokSzczegolow({
  wniosek,
  wszystkieWnioski,
  onZapisz,
  onUsun,
}: {
  wniosek: Wniosek;
  wszystkieWnioski: Wniosek[];
  onZapisz: (dane: Omit<Wniosek, 'id'>) => Promise<Wniosek>;
  onUsun: () => Promise<void>;
}) {
  const nav = useNavigate();
  const dzis = dzisIso();

  const [dane, setDane] = useState({
    numer: wniosek.numer,
    dataWplywu: wniosek.dataWplywu,
    inicjaly: wniosek.inicjaly,
    wnioskodawca: wniosek.wnioskodawca,
    kontakt: wniosek.kontakt ?? '',
    temat: wniosek.temat,
    tresc: wniosek.tresc,
    status: wniosek.status,
    dniKwerendy: wniosek.dniKwerendy ?? 14,
    dataOdpowiedzi: wniosek.dataOdpowiedzi ?? '',
  });
  const [trwaZapis, setTrwaZapis] = useState(false);
  const [blad, setBlad] = useState('');
  const [info, setInfo] = useState('');

  const ustaw = <K extends keyof typeof dane>(k: K, v: (typeof dane)[K]) => {
    setInfo('');
    setDane((d) => ({ ...d, [k]: v }));
  };

  function zmienStatus(nowy: Status) {
    setInfo('');
    setDane((d) => ({
      ...d,
      status: nowy,
      dataOdpowiedzi: nowy === 'odpowiedz_wyslana' ? d.dataOdpowiedzi || dzis : d.dataOdpowiedzi,
      dniKwerendy: nowy === 'kwerenda' ? d.dniKwerendy || 14 : d.dniKwerendy,
    }));
  }

  const aktualnyWniosek: Wniosek = {
    ...wniosek,
    numer: dane.numer,
    dataWplywu: dane.dataWplywu,
    inicjaly: dane.inicjaly.toUpperCase(),
    wnioskodawca: dane.wnioskodawca,
    kontakt: dane.kontakt || undefined,
    temat: dane.temat,
    tresc: dane.tresc,
    status: dane.status,
    dniKwerendy: dane.status === 'kwerenda' ? dane.dniKwerendy : undefined,
    dataOdpowiedzi: dane.status === 'odpowiedz_wyslana' ? dane.dataOdpowiedzi || undefined : undefined,
  };

  const ocenaTerminu = pilnosc(aktualnyWniosek, dzis);
  const duplikat = wszystkieWnioski.some((w) => w.id !== wniosek.id && w.numer === dane.numer.trim());
  const zmieniono =
    dane.numer.trim() !== wniosek.numer ||
    dane.dataWplywu !== wniosek.dataWplywu ||
    dane.inicjaly.trim().toUpperCase() !== wniosek.inicjaly ||
    dane.wnioskodawca.trim() !== wniosek.wnioskodawca ||
    (dane.kontakt.trim() || undefined) !== wniosek.kontakt ||
    dane.temat.trim() !== wniosek.temat ||
    dane.tresc !== wniosek.tresc ||
    dane.status !== wniosek.status ||
    (dane.status === 'kwerenda' ? dane.dniKwerendy : undefined) !== wniosek.dniKwerendy ||
    (dane.status === 'odpowiedz_wyslana' ? dane.dataOdpowiedzi || undefined : undefined) !== wniosek.dataOdpowiedzi;

  const gotowe = !!dane.numer.trim() && !!dane.dataWplywu && !!dane.temat.trim() && !duplikat;

  async function zapisz() {
    setTrwaZapis(true);
    setBlad('');
    setInfo('');
    try {
      zapamietajInicjaly(dane.inicjaly.trim());
      await onZapisz({
        numer: dane.numer.trim(),
        dataWplywu: dane.dataWplywu,
        inicjaly: dane.inicjaly.trim().toUpperCase(),
        wnioskodawca: dane.wnioskodawca.trim(),
        kontakt: dane.kontakt.trim() || undefined,
        temat: dane.temat.trim(),
        tresc: dane.tresc,
        status: dane.status,
        dniKwerendy: dane.status === 'kwerenda' ? dane.dniKwerendy : undefined,
        dataOdpowiedzi: dane.status === 'odpowiedz_wyslana' ? dane.dataOdpowiedzi || undefined : undefined,
        nazwaPliku: wniosek.nazwaPliku,
      });
      setInfo('Zapisano zmiany.');
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    } finally {
      setTrwaZapis(false);
    }
  }

  async function usun() {
    if (!confirm(`Usunąć wniosek ${wniosek.numer}?`)) return;
    setTrwaZapis(true);
    setBlad('');
    try {
      await onUsun();
      nav('/');
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
      setTrwaZapis(false);
    }
  }

  return (
    <>
      <div className="rzad rozsun" style={{ marginBottom: 18 }}>
        <div className="rzad">
          <Link className="przycisk maly-p" to="/">← Wnioski</Link>
          <h1 style={{ margin: 0 }}>{dane.numer || 'Szczegóły wniosku'}</h1>
          <ZnaczekStatusu status={dane.status} dniKwerendy={dane.status === 'kwerenda' ? dane.dniKwerendy : undefined} />
          <Pozostalo pilnosc={ocenaTerminu.pilnosc} pozostalo={ocenaTerminu.pozostalo} />
        </div>
        <div className="rzad">
          {dane.status === 'odpowiedz_wyslana' && (
            <Link
              className="przycisk maly-p"
              to="/archiwum/nowa"
              state={{ sygnatura: dane.numer, wniosek: dane.tresc, dataOdpowiedzi: dane.dataOdpowiedzi || undefined } satisfies ZWniosku}
            >
              Dodaj do archiwum
            </Link>
          )}
        </div>
      </div>

      <div className="siatka-2">
        <div className="stos">
          <div className="karta">
            <h2>Dane wniosku</h2>
            <div className="formularz">
              <label>
                Nr wniosku
                <input value={dane.numer} onChange={(e) => ustaw('numer', e.target.value)} />
                {duplikat && <span style={{ color: 'var(--czerwony)' }}>Taki numer już istnieje</span>}
              </label>
              <label>
                Data wpływu
                <input type="date" value={dane.dataWplywu} onChange={(e) => ustaw('dataWplywu', e.target.value)} />
                {dane.dataWplywu && (
                  <span>
                    Termin odpowiedzi: <strong>{formatuj(terminOdpowiedzi(aktualnyWniosek))}</strong>
                  </span>
                )}
              </label>
              <label>
                Wnioskodawca
                <input value={dane.wnioskodawca} onChange={(e) => ustaw('wnioskodawca', e.target.value)} />
              </label>
              <label>
                Adres do odpowiedzi (e-mail / adres)
                <input value={dane.kontakt} onChange={(e) => ustaw('kontakt', e.target.value)} />
              </label>
              <label className="pelny">
                Skrócony opis tematu
                <input value={dane.temat} onChange={(e) => ustaw('temat', e.target.value)} />
              </label>
              <label>
                Inicjały osoby prowadzącej
                <input value={dane.inicjaly} maxLength={4} onChange={(e) => ustaw('inicjaly', e.target.value)} />
              </label>
              <label>
                Status
                <select value={dane.status} onChange={(e) => zmienStatus(e.target.value as Status)}>
                  {STATUSY.map((s) => <option key={s.id} value={s.id}>{s.etykieta}</option>)}
                </select>
              </label>
              {dane.status === 'kwerenda' && (
                <label>
                  Dodatkowe dni kwerendy
                  <input
                    type="number"
                    min={1}
                    max={dane.dataWplywu ? maksDniKwerendy(dane.dataWplywu) : 47}
                    value={dane.dniKwerendy}
                    onChange={(e) => ustaw('dniKwerendy', Math.max(1, Number(e.target.value) || 1))}
                  />
                </label>
              )}
              {dane.status === 'odpowiedz_wyslana' && (
                <label>
                  Data odpowiedzi
                  <input type="date" value={dane.dataOdpowiedzi} onChange={(e) => ustaw('dataOdpowiedzi', e.target.value)} />
                </label>
              )}
              {wniosek.nazwaPliku && (
                <div className="pelny maly">
                  Plik: <strong>{wniosek.nazwaPliku}</strong>
                </div>
              )}
              <label className="pelny">
                Treść wniosku
                <textarea rows={10} value={dane.tresc} onChange={(e) => ustaw('tresc', e.target.value)} />
              </label>
            </div>
            {blad && <div className="blad" style={{ marginTop: 12 }}>{blad}</div>}
            {info && <div className="info" style={{ marginTop: 12 }}>{info}</div>}
            <div className="rzad" style={{ marginTop: 14 }}>
              <button className="glowny" disabled={trwaZapis || !gotowe || !zmieniono} onClick={() => void zapisz()}>
                {trwaZapis ? 'Zapisywanie…' : 'Zapisz zmiany'}
              </button>
              <button disabled={trwaZapis} onClick={() => void usun()} style={{ color: 'var(--czerwony)' }}>
                Usuń
              </button>
            </div>
          </div>
        </div>

        <div className="stos">
          <PropozycjaOdpowiedzi
            key={wniosek.id}
            wniosek={{
              tresc: dane.tresc,
              temat: dane.temat,
              numer: dane.numer,
              data_wplywu: dane.dataWplywu,
              wnioskodawca: dane.wnioskodawca,
            }}
          />
        </div>
      </div>
    </>
  );
}
