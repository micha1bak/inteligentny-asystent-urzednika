import { useRef, useState } from 'react';
import { pobierzPropozycje, type Propozycja, type ZapytanieOPropozycje } from '../lib/api';
import PodstawyPrawne from './PodstawyPrawne';

/** Propozycja odpowiedzi z modelu (Groq) na podstawie modelu oceny prawnej i archiwum werdyktów. */
export default function PropozycjaOdpowiedzi({ wniosek }: { wniosek: ZapytanieOPropozycje }) {
  const [wynik, setWynik] = useState<Propozycja>();
  const [podstawy, setPodstawy] = useState<string[]>([]);
  const [projekt, setProjekt] = useState('');
  const [blad, setBlad] = useState('');
  const [trwa, setTrwa] = useState(false);
  const [skopiowano, setSkopiowano] = useState(false);
  const przerwij = useRef<AbortController | null>(null);
  const projektRef = useRef<HTMLTextAreaElement | null>(null);

  const mozna = wniosek.tresc.trim().length >= 20;

  async function generuj() {
    przerwij.current?.abort();
    const ac = new AbortController();
    przerwij.current = ac;
    setTrwa(true);
    setBlad('');
    try {
      const p = await pobierzPropozycje(wniosek, ac.signal);
      setWynik(p);
      setPodstawy(p.podstawy_prawne);
      setProjekt(p.projekt_odpowiedzi);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) setBlad(e instanceof Error ? e.message : String(e));
    } finally {
      if (przerwij.current === ac) setTrwa(false);
    }
  }

  function dodajPodstawe(etykieta: string) {
    setPodstawy((prev) => (prev.includes(etykieta) ? prev : [...prev, etykieta]));
  }

  function wstawDoPisma(fragment: string) {
    const pole = projektRef.current;
    if (!pole) {
      setProjekt((prev) => (prev ? `${prev}\n${fragment}` : fragment));
      return;
    }
    const start = pole.selectionStart ?? projekt.length;
    const koniec = pole.selectionEnd ?? projekt.length;
    setProjekt((prev) => {
      const przed = prev.slice(0, start);
      const po = prev.slice(koniec);
      const separatorPrzed = przed && !/[\s(„"]$/.test(przed) ? ' ' : '';
      const separatorPo = po && !/^[\s.,;:!?)"”]/.test(po) ? ' ' : '';
      return `${przed}${separatorPrzed}${fragment}${separatorPo}${po}`;
    });
    pole.focus();
  }

  async function kopiuj() {
    try {
      await navigator.clipboard.writeText(projekt);
      setSkopiowano(true);
      setTimeout(() => setSkopiowano(false), 1500);
    } catch {
      /* brak uprawnień do schowka – urzędnik może zaznaczyć tekst ręcznie */
    }
  }

  return (
    <div className="karta">
      <div className="rzad rozsun">
        <h2 style={{ margin: 0 }}>Propozycja odpowiedzi (AI)</h2>
        <button className={wynik ? 'maly-p' : 'glowny'} disabled={!mozna || trwa} onClick={() => void generuj()}>
          {trwa ? 'Analizuję wniosek…' : wynik ? 'Wygeneruj ponownie' : 'Zaproponuj odpowiedź'}
        </button>
      </div>
      <p className="maly" style={{ margin: '8px 0 12px' }}>
        Treść wniosku, model oceny prawnej (UDIP, KPA, Zarządzenie 535/2024) i archiwum werdyktów są wysyłane do modelu w Groq.
        Używaj tylko danych testowych. To projekt – decyzję podejmuje urzędnik.
      </p>
      {!mozna && <p className="maly">Najpierw wgraj wniosek z czytelną treścią.</p>}
      {trwa && <div className="postep postep-ciagly"><div /></div>}
      {blad && <div className="blad">{blad}</div>}

      {!wynik && !trwa && (
        <div style={{ marginTop: 10 }}>
          <PodstawyPrawne
            podstawy={podstawy}
            onDodajPodstawe={dodajPodstawe}
            tytul="Podstawy prawne – szybki podgląd ustaw (bez AI)"
          />
        </div>
      )}

      {wynik && !trwa && (
        <div className="stos" style={{ gap: 12 }}>
          {wynik.ostrzezenia.map((o) => <div key={o} className="uwaga">{o}</div>)}
          <div>
            <div className="maly">Proponowane rozstrzygnięcie</div>
            <strong>{wynik.werdykt.replaceAll('_', ' ').toLowerCase()}</strong>
            {wynik.werdykt_opis && <div className="maly">{wynik.werdykt_opis}</div>}
          </div>
          <div>
            <div className="maly">Uzasadnienie</div>
            <div style={{ fontSize: '0.92rem' }}>{wynik.uzasadnienie}</div>
          </div>
          {wynik.komorka_merytoryczna && (
            <div>
              <div className="maly">Komórka merytoryczna</div>
              <div style={{ fontSize: '0.92rem' }}>{wynik.komorka_merytoryczna}</div>
            </div>
          )}
          <PodstawyPrawne
            podstawy={podstawy}
            onDodajPodstawe={dodajPodstawe}
            onWstawDoPisma={wstawDoPisma}
          />
          <Lista tytul="Podobne sprawy z archiwum" elementy={wynik.podobne_sprawy.map((s) => `${s.sygnatura} – ${s.dlaczego}`)} />
          <Lista tytul="Do anonimizacji" elementy={wynik.dane_do_anonimizacji} />
          <Lista tytul="Do sprawdzenia przez urzędnika" elementy={wynik.do_weryfikacji} />
          <label>
            {wynik.wzor_nazwa ? `Projekt pisma – wzór: ${wynik.wzor_nazwa} (możesz edytować)` : 'Projekt pisma (możesz edytować)'}
            <textarea
              ref={projektRef}
              rows={16}
              value={projekt}
              onChange={(e) => setProjekt(e.target.value)}
              style={{ fontFamily: "'Times New Roman', serif", fontSize: '0.98rem' }}
            />
          </label>
          <div className="rzad">
            <button className="maly-p" onClick={() => void kopiuj()}>{skopiowano ? 'Skopiowano' : 'Kopiuj projekt'}</button>
            <span className="maly">model: {wynik.model}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function Lista({ tytul, elementy }: { tytul: string; elementy: string[] }) {
  if (!elementy.length) return null;
  return (
    <div>
      <div className="maly">{tytul}</div>
      <ul style={{ margin: '4px 0 0', paddingLeft: 18, fontSize: '0.9rem' }}>
        {elementy.map((e) => <li key={e}>{e}</li>)}
      </ul>
    </div>
  );
}
