import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import logo from '../assets/logo-bydgoszcz.png';
import { podzielNaUkrycia, przelaczUkrycie, type Ukrycie } from '../lib/anonimizacja';
import {
  fragmentyZnacznikow, przeniesZakres, przesunBlok, rozlozNaStrony, usunBlok, wstawBlok, zakresBloku, type Kawalek, type StrukturaPisma,
} from '../lib/pismo';

// Wymiary w punktach typograficznych, zmierzone na oryginalnych pismach BKS (A4 = 595,3 × 841,9 pt).
const PT = 4 / 3; // 1 pt = 4/3 px (CSS)
const SZEROKOSC_STRONY = 595.3;
const WYSOKOSC_STRONY = 841.9;
const ODSTEP_STRON = 16; // px
const WYSOKOSC_TRESCI = 637; // od y = 93 pt (początek linii daty) do y = 730 pt (nad stopką)
const LINIA = 20.7; // interlinia treści

type Zakres = { od: number; do: number };
type Element = {
  klucz: string;
  /** zakres słów – gdy akapit jest podzielony między strony */
  tresc: (edycja: boolean, zakres?: Zakres) => ReactNode;
  trzymajZNastepnym?: boolean;
  slowa?: string[];
  /** indeks bloku w `pismo.tresc` – tylko bloki treści można przestawiać */
  blok?: number;
};

/** Przestawianie bloków treści (przeciąganie, ↑ ↓, dodawanie, usuwanie) – tylko na ekranie, nie na wydruku. */
type Przestawianie = {
  przeciagany: number | null;
  /** zakres przeciąganych bloków [od, do) – „Ad n” razem z odpowiedzią */
  zakres: [number, number] | null;
  cel: number | null; // blok zostanie wstawiony przed blokiem o tym indeksie (n = na koniec)
  start: (i: number) => void;
  nad: (przed: number) => void;
  upusc: () => void;
  koniec: () => void;
  przesun: (i: number, o: -1 | 1) => void;
  dodaj: (i: number) => void;
  usun: (i: number) => void;
  liczba: number;
};

/** Anonimizacja w podglądzie: propozycje (szare) i ukryte (czarne); w trybie anonimizacji kliknięcie przełącza stan. */
const KontekstUkryc = createContext<{ ukrycia: Ukrycie[]; tryb: boolean; przelacz: (tekst: string) => void }>({
  ukrycia: [],
  tryb: false,
  przelacz: () => {},
});

/**
 * Podgląd pisma w układzie oryginalnych pism Biura Komunikacji Społecznej:
 * strona A4, logo i nagłówek, ramka, stopka na każdej stronie, automatyczny podział na strony.
 * Tekst można poprawiać bezpośrednio na podglądzie (zmiany trafiają do `onZmiana`).
 */
export default function PodgladPisma({ pismo, onZmiana, trybAnonimizacji = false }: {
  pismo: StrukturaPisma;
  onZmiana: (p: StrukturaPisma) => void;
  /** tryb anonimizacji: tekst nieedytowalny, kliknięcie fragmentu ukrywa go / przywraca jako propozycję */
  trybAnonimizacji?: boolean;
}) {
  const pomiar = useRef<HTMLDivElement>(null);
  const miarka = useRef<HTMLDivElement>(null);
  const kontener = useRef<HTMLDivElement>(null);
  const [strony, setStrony] = useState<Kawalek[][] | null>(null);
  const [skala, setSkala] = useState(1);
  const [czcionki, setCzcionki] = useState(0);

  const zmien = (zmiana: Partial<StrukturaPisma>) => onZmiana({ ...pismo, ...zmiana });
  const elementy = budujElementy(pismo, zmien);

  const [przeciagany, setPrzeciagany] = useState<number | null>(null);
  const [cel, setCel] = useState<number | null>(null);
  const przestawianie: Przestawianie = {
    przeciagany,
    zakres: przeciagany === null ? null : zakresBloku(pismo.tresc, przeciagany),
    cel,
    liczba: pismo.tresc.length,
    start: (i) => setPrzeciagany(i),
    nad: (przed) => setCel(przed),
    upusc: () => {
      if (przeciagany !== null && cel !== null) {
        const [od, do_] = zakresBloku(pismo.tresc, przeciagany); // „Ad n” razem z odpowiedzią
        zmien({ tresc: przeniesZakres(pismo.tresc, od, do_, cel) });
      }
      setPrzeciagany(null);
      setCel(null);
    },
    koniec: () => {
      setPrzeciagany(null);
      setCel(null);
    },
    przesun: (i, o) => zmien({ tresc: przesunBlok(pismo.tresc, i, o) }),
    dodaj: (i) => zmien({ tresc: wstawBlok(pismo.tresc, i, { typ: 'akapit', tekst: '' }) }),
    usun: (i) => zmien({ tresc: usunBlok(pismo.tresc, i) }),
  };

  // wysokości elementów (renderowanych poza ekranem w szerokości obszaru treści) -> podział na strony
  useLayoutEffect(() => {
    const dzieci = pomiar.current?.children;
    const akapit = miarka.current;
    if (!dzieci || !akapit || dzieci.length !== elementy.length) return;
    const mierz = (slowa: string[]) => {
      akapit.textContent = slowa.join(' ');
      return akapit.offsetHeight;
    };
    const uklad = elementy.map((e, i) => ({
      wysokosc: (dzieci[i] as HTMLElement).offsetHeight,
      trzymajZNastepnym: e.trzymajZNastepnym,
      slowa: e.slowa,
    }));
    setStrony(rozlozNaStrony(uklad, WYSOKOSC_TRESCI * PT, mierz, 2 * LINIA * PT));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- elementy wynikają z `pismo`
  }, [pismo, czcionki]);

  useEffect(() => {
    void document.fonts?.ready.then(() => setCzcionki((n) => n + 1));
  }, []);

  // dopasowanie skali strony do szerokości karty
  useEffect(() => {
    const el = kontener.current;
    if (!el) return;
    const obs = new ResizeObserver(([w]) => setSkala(Math.min(1, w.contentRect.width / (SZEROKOSC_STRONY * PT))));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const uklad: Kawalek[][] =
    strony && strony.every((s) => s.every((k) => k.i < elementy.length)) ? strony : [elementy.map((_, i) => ({ i }))];

  const ukrycia = pismo.ukrycia ?? [];
  const kontekstUkryc = {
    ukrycia,
    tryb: trybAnonimizacji,
    przelacz: (tekst: string) => onZmiana({ ...pismo, ukrycia: przelaczUkrycie(ukrycia, tekst) }),
  };

  return (
    <KontekstUkryc.Provider value={kontekstUkryc}>
    <div ref={kontener} className={`podglad-pisma${trybAnonimizacji ? ' tryb-anonimizacji' : ''}`}>
      {/* transform (nie zoom): skalowanie nie zmienia łamania linii, więc pomiar wysokości zgadza się z widokiem */}
      <div
        className="podglad-skala"
        style={{
          width: SZEROKOSC_STRONY * PT * skala,
          height: (uklad.length * WYSOKOSC_STRONY * PT + (uklad.length - 1) * ODSTEP_STRON) * skala,
        }}
      >
        <div className="ekran-pisma" style={{ transform: `scale(${skala})`, gap: ODSTEP_STRON }}>
          <Strony pismo={pismo} elementy={elementy} uklad={uklad} edycja przestawianie={przestawianie} />
        </div>
      </div>
      {/* kopia do druku: bezpośrednio w <body>, bez skalowania i bez układu aplikacji (widoczna tylko przy drukowaniu) */}
      {createPortal(
        <div className="druk-pisma">
          <Strony pismo={pismo} elementy={elementy} uklad={uklad} edycja={false} />
        </div>,
        document.body,
      )}
      {/* niewidoczna kopia treści do pomiaru wysokości elementów */}
      <div ref={pomiar} className="strona-tresc pomiar-pisma" aria-hidden>
        {elementy.map((e) => <div key={e.klucz}>{e.tresc(false)}</div>)}
      </div>
      <div className="strona-tresc pomiar-pisma" aria-hidden>
        <div ref={miarka} className="p-akapit" />
      </div>
    </div>
    </KontekstUkryc.Provider>
  );
}

function Strony({ pismo, elementy, uklad, edycja, przestawianie }: {
  pismo: StrukturaPisma;
  elementy: Element[];
  uklad: Kawalek[][];
  edycja: boolean;
  przestawianie?: Przestawianie;
}) {
  return (
    <>
      {uklad.map((kawalki, nr) => (
        <section key={nr} className="strona-a4" aria-label={`Strona ${nr + 1} z ${uklad.length}`}>
          <header className="strona-naglowek">
            <img src={logo} alt="Bydgoszcz" />
            <div>{pismo.naglowek.map((l) => <div key={l}>{l}</div>)}</div>
          </header>
          <div className="strona-ramka-pozioma" />
          <div className="strona-ramka-pionowa" />
          <div className="strona-tresc">
            {kawalki.map((k) => {
              const el = elementy[k.i];
              const tresc = el.tresc(edycja, k.od !== undefined && k.do !== undefined ? { od: k.od, do: k.do } : undefined);
              if (!przestawianie || el.blok === undefined) return <div key={`${el.klucz}-${k.od ?? 0}`}>{tresc}</div>;
              return (
                <Klocek key={`${el.klucz}-${k.od ?? 0}`} blok={el.blok} poczatek={(k.od ?? 0) === 0} p={przestawianie}>
                  {tresc}
                </Klocek>
              );
            })}
          </div>
          <footer className="strona-stopka">{pismo.stopka.map((l) => <div key={l}>{l}</div>)}</footer>
          {edycja && uklad.length > 1 && <div className="strona-numer">{nr + 1}/{uklad.length}</div>}
        </section>
      ))}
    </>
  );
}

function budujElementy(p: StrukturaPisma, zmien: (z: Partial<StrukturaPisma>) => void): Element[] {
  const zamien = <T,>(lista: T[], i: number, w: T) => lista.map((x, j) => (j === i ? w : x));
  const el: Element[] = [
    { klucz: 'data', tresc: (e) => <Tekst klasa="p-data" tekst={p.data} edycja={e} onZmiana={(t) => zmien({ data: t })} /> },
    { klucz: 'znak', tresc: (e) => <Tekst klasa="p-znak" tekst={p.znak} edycja={e} onZmiana={(t) => zmien({ znak: t })} /> },
    {
      klucz: 'adres',
      tresc: (e) => (
        <div className="p-adres">
          <Tekst
            klasa="p-adresat"
            tekst={p.adresat.join('\n')}
            wieleLinii
            podpowiedz="[adresat – kliknij, aby wpisać]"
            edycja={e}
            onZmiana={(t) => zmien({ adresat: t.split('\n').map((l) => l.trim()).filter(Boolean) })}
          />
        </div>
      ),
    },
  ];
  if (p.tytul.length) {
    el.push({
      klucz: 'tytul',
      tresc: (e) => (
        <div className="p-tytul">
          {p.tytul.map((l, i) => <Tekst key={i} tekst={l} edycja={e} onZmiana={(t) => zmien({ tytul: zamien(p.tytul, i, t) })} />)}
        </div>
      ),
    });
  }
  p.tresc.forEach((b, i) => {
    const ustaw = (t: string) => zmien({ tresc: zamien(p.tresc, i, { ...b, tekst: t }) });
    const slowa = b.typ === 'akapit' ? b.tekst.split(/\s+/).filter(Boolean) : undefined;
    el.push({
      klucz: `t${i}`,
      blok: i,
      trzymajZNastepnym: b.typ === 'ad' || b.typ === 'zwrot',
      slowa,
      tresc: (e, zakres) => {
        if (!zakres || !slowa) {
          return <Tekst klasa={`p-${b.typ}`} tekst={b.tekst} edycja={e} onZmiana={ustaw} podpowiedz="[nowy akapit – kliknij, aby wpisać]" />;
        }
        // fragment akapitu podzielonego między strony; edycja podmienia tylko ten fragment
        const ciag = zakres.do < slowa.length ? ' p-ciag' : '';
        return (
          <Tekst
            klasa={`p-akapit${ciag}`}
            tekst={slowa.slice(zakres.od, zakres.do).join(' ')}
            edycja={e}
            onZmiana={(t) => ustaw([...slowa.slice(0, zakres.od), t, ...slowa.slice(zakres.do)].filter(Boolean).join(' '))}
          />
        );
      },
    });
  });
  el.push({
    klucz: 'koniec',
    tresc: (e) => (
      <div className="p-koniec">
        <Tekst tekst={p.zakonczenie} edycja={e} onZmiana={(t) => zmien({ zakonczenie: t })} />
        <div className="p-podpis">
          {p.podpis.map((l, i) => <Tekst key={i} tekst={l} edycja={e} onZmiana={(t) => zmien({ podpis: zamien(p.podpis, i, t) })} />)}
        </div>
      </div>
    ),
  });
  return el;
}

/** Edytowalny fragment pisma; znaczniki [[…]] są wyróżnione (tylko na ekranie). */
function Tekst({ tekst, onZmiana, edycja, klasa = '', wieleLinii = false, podpowiedz }: {
  tekst: string;
  onZmiana: (t: string) => void;
  edycja: boolean;
  klasa?: string;
  wieleLinii?: boolean;
  podpowiedz?: string;
}) {
  const { ukrycia, tryb, przelacz } = useContext(KontekstUkryc);
  const klikalne = edycja && tryb;
  const zawartosc = tekst.split('\n').map((linia, i) => (
    <span key={i}>
      {i > 0 && <br />}
      {podzielNaUkrycia(linia, ukrycia).map((o, j) =>
        o.ukrycie ? (
          <span
            key={j}
            className={`anon anon-${o.ukrycie.stan}`}
            title={`${o.ukrycie.rodzaj}${klikalne ? (o.ukrycie.stan === 'ukryte' ? ' – kliknij, aby przywrócić' : ' – kliknij, aby ukryć') : ''}`}
            onClick={klikalne ? () => przelacz(o.ukrycie!.tekst) : undefined}
          >
            {/* wydruk / zapis PDF: ukryty tekst ZASTĄPIONY znakami █ – nie da się go skopiować z pliku */}
            {!edycja && o.ukrycie.stan === 'ukryte' ? '█'.repeat(o.tekst.length) : o.tekst}
          </span>
        ) : (
          fragmentyZnacznikow(o.tekst).map((f, k) => (f.znacznik ? <mark key={`${j}-${k}`} className="p-znacznik">{f.tekst}</mark> : f.tekst))
        ),
      )}
    </span>
  ));
  if (!edycja || tryb) return <div className={klasa}>{tekst ? zawartosc : ' '}</div>;
  return (
    <div
      key={tekst /* po zmianie tekstu element jest tworzony od nowa – React nie walczy z contentEditable */}
      className={`${klasa} p-edytowalny`}
      contentEditable
      suppressContentEditableWarning
      spellCheck
      data-podpowiedz={podpowiedz}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && !wieleLinii) {
          e.preventDefault();
          e.currentTarget.blur();
        }
      }}
      onBlur={(e) => {
        const surowy = e.currentTarget.innerText.replace(/ /g, ' ');
        const nowy = wieleLinii ? surowy.trim() : surowy.replace(/\s*\n\s*/g, ' ').trim();
        if (nowy !== tekst) onZmiana(nowy);
      }}
    >
      {tekst ? zawartosc : null}
    </div>
  );
}

/**
 * Blok treści z paskiem narzędzi na lewym marginesie strony: uchwyt do przeciągania, ↑ ↓, ＋ (nowy akapit poniżej), ✕.
 * Upuszczenie w górnej połowie bloku wstawia przeciągany blok przed nim, w dolnej – po nim.
 */
function Klocek({ blok, poczatek, p, children }: { blok: number; poczatek: boolean; p: Przestawianie; children: ReactNode }) {
  const klasy = ['klocek'];
  if (p.zakres && blok >= p.zakres[0] && blok < p.zakres[1]) klasy.push('klocek-przeciagany');
  if (p.przeciagany !== null && p.cel === blok) klasy.push('klocek-cel-przed');
  if (p.przeciagany !== null && p.cel === blok + 1 && blok === p.liczba - 1) klasy.push('klocek-cel-po');
  const bezKlikniecia = (e: ReactMouseEvent) => e.preventDefault(); // nie zabieraj fokusu edytowanemu tekstowi
  return (
    <div
      className={klasy.join(' ')}
      onDragOver={(e) => {
        if (p.przeciagany === null) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const r = e.currentTarget.getBoundingClientRect();
        p.nad(e.clientY < r.top + r.height / 2 ? blok : blok + 1);
      }}
      onDrop={(e) => {
        e.preventDefault();
        p.upusc();
      }}
    >
      {poczatek && (
        <div className="klocek-narzedzia" aria-label="Przestawianie bloku">
          <span
            className="klocek-uchwyt"
            draggable
            title="Przeciągnij, aby przestawić blok"
            onDragStart={(e) => {
              e.dataTransfer.effectAllowed = 'move';
              e.dataTransfer.setData('text/plain', String(blok));
              p.start(blok);
            }}
            onDragEnd={p.koniec}
          >⋮⋮</span>
          <button type="button" title="Przesuń wyżej" disabled={blok === 0} onMouseDown={bezKlikniecia} onClick={() => p.przesun(blok, -1)}>↑</button>
          <button type="button" title="Przesuń niżej" disabled={blok === p.liczba - 1} onMouseDown={bezKlikniecia} onClick={() => p.przesun(blok, 1)}>↓</button>
          <button type="button" title="Dodaj akapit poniżej" onMouseDown={bezKlikniecia} onClick={() => p.dodaj(blok)}>＋</button>
          <button type="button" title="Usuń blok" onMouseDown={bezKlikniecia} onClick={() => p.usun(blok)}>✕</button>
        </div>
      )}
      {children}
    </div>
  );
}
