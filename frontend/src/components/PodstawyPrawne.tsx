import { useEffect, useState, type FormEvent } from 'react';
import {
  pobierzDokumentyPrawne,
  szukajPrzepisow,
  type DokumentPrawnyInfo,
  type FragmentPrzepisu,
  type WynikWyszukiwaniaPrzepisow,
} from '../lib/api';

interface Props {
  podstawy: string[];
  onDodajPodstawe?: (etykieta: string) => void;
  onWstawDoPisma?: (tekst: string) => void;
  tytul?: string;
}

interface StanPodgladu {
  trwa: boolean;
  blad: string;
  dane?: WynikWyszukiwaniaPrzepisow;
}

const OPIS_DOPASOWANIA: Record<FragmentPrzepisu['dopasowanie'], string> = {
  dokladne: 'dokładny fragment',
  artykul: 'cały artykuł / paragraf',
  tekstowe: 'dopasowanie tekstowe',
};

/**
 * Sekcja „Podstawy prawne” z deterministycznym podglądem treści ustępów/artykułów/paragrafów
 * z folderu „Dokumenty i podstawy prawne” (bez użycia modelu AI) oraz wyszukiwarką ręczną.
 */
export default function PodstawyPrawne({
  podstawy,
  onDodajPodstawe,
  onWstawDoPisma,
  tytul = 'Podstawy prawne',
}: Props) {
  const [otwarte, setOtwarte] = useState<Record<string, boolean>>({});
  const [podglady, setPodglady] = useState<Record<string, StanPodgladu>>({});
  const [wyszukiwarkaOtwarta, setWyszukiwarkaOtwarta] = useState(false);

  const [dokumenty, setDokumenty] = useState<DokumentPrawnyInfo[]>([]);
  const [zapytanie, setZapytanie] = useState('');
  const [wybranyAkt, setWybranyAkt] = useState('');
  const [wynikSzukania, setWynikSzukania] = useState<WynikWyszukiwaniaPrzepisow>();
  const [trwaSzukanie, setTrwaSzukanie] = useState(false);
  const [bladSzukania, setBladSzukania] = useState('');

  useEffect(() => {
    if (!wyszukiwarkaOtwarta || dokumenty.length > 0) return;
    const ac = new AbortController();
    pobierzDokumentyPrawne(ac.signal)
      .then((d) => setDokumenty(d))
      .catch(() => {
        /* lista dokumentów jest opcjonalna do filtrowania */
      });
    return () => ac.abort();
  }, [wyszukiwarkaOtwarta, dokumenty.length]);

  async function przelaczPodglad(podstawa: string) {
    const czyOtwarte = !!otwarte[podstawa];
    setOtwarte((prev) => ({ ...prev, [podstawa]: !czyOtwarte }));
    if (czyOtwarte) return;
    if (podglady[podstawa]?.dane) return;

    setPodglady((prev) => ({ ...prev, [podstawa]: { trwa: true, blad: '' } }));
    try {
      const dane = await szukajPrzepisow(podstawa, undefined, 8);
      setPodglady((prev) => ({ ...prev, [podstawa]: { trwa: false, blad: '', dane } }));
    } catch (e) {
      setPodglady((prev) => ({
        ...prev,
        [podstawa]: { trwa: false, blad: e instanceof Error ? e.message : String(e) },
      }));
    }
  }

  async function wykonajSzukanie(e: FormEvent) {
    e.preventDefault();
    const q = zapytanie.trim();
    if (!q) return;
    setTrwaSzukanie(true);
    setBladSzukania('');
    try {
      const dane = await szukajPrzepisow(q, wybranyAkt || undefined, 8);
      setWynikSzukania(dane);
    } catch (err) {
      setBladSzukania(err instanceof Error ? err.message : String(err));
    } finally {
      setTrwaSzukanie(false);
    }
  }

  return (
    <div className="podstawy-sekcja">
      <div className="rzad rozsun">
        <div className="maly">{tytul}</div>
        <button
          type="button"
          className="maly-p"
          onClick={() => setWyszukiwarkaOtwarta((v) => !v)}
        >
          {wyszukiwarkaOtwarta ? 'Ukryj wyszukiwarkę ustaw' : 'Szukaj ustępu w dokumentach'}
        </button>
      </div>

      {podstawy.length > 0 && (
        <ul className="podstawy-lista">
          {podstawy.map((p) => {
            const otwarty = !!otwarte[p];
            const stan = podglady[p];
            return (
              <li key={p} className="podstawa-pozycja">
                <div className="podstawa-naglowek">
                  <span>{p}</span>
                  <button
                    type="button"
                    className="maly-p podstawa-przycisk"
                    onClick={() => void przelaczPodglad(p)}
                  >
                    {otwarty ? 'Ukryj treść' : 'Odwołanie / treść'}
                  </button>
                </div>

                {otwarty && (
                  <div className="podstawa-podglad">
                    {stan?.trwa && <div className="maly">Wyszukuję…</div>}
                    {stan?.blad && <div className="blad">{stan.blad}</div>}
                    {stan?.dane && stan.dane.wyniki.length === 0 && (
                      <div className="maly">
                        Nie znaleziono fragmentu dla „{p}” w lokalnych plikach
                        {stan.dane.dostepne_pliki.length > 0
                          ? ` (${stan.dane.dostepne_pliki.join(', ')})`
                          : ''}
                        .
                      </div>
                    )}
                    {stan?.dane?.wyniki.map((frag) => (
                      <KartaFragmentu
                        key={`${frag.plik}-${frag.etykieta}-${frag.strona ?? ''}`}
                        fragment={frag}
                        onWstawDoPisma={onWstawDoPisma}
                      />
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {wyszukiwarkaOtwarta && (
        <div className="wyszukiwarka-przepisow">
          <form className="wyszukiwarka-pasek" onSubmit={(e) => void wykonajSzukanie(e)}>
            <input
              value={zapytanie}
              onChange={(e) => setZapytanie(e.target.value)}
              placeholder="np. Art. 13 ust. 2 UDIP, § 11 ust. 3, Art. 64 § 2 KPA lub fraza…"
              aria-label="Szukaj przepisu lub frazy"
            />
            {dokumenty.length > 0 && (
              <select
                value={wybranyAkt}
                onChange={(e) => setWybranyAkt(e.target.value)}
                aria-label="Filtr dokumentu"
              >
                <option value="">Wszystkie dokumenty</option>
                {dokumenty.map((d) => (
                  <option key={d.plik} value={d.akt}>
                    {d.nazwa}
                  </option>
                ))}
              </select>
            )}
            <button type="submit" className="maly-p glowny" disabled={trwaSzukanie || !zapytanie.trim()}>
              {trwaSzukanie ? 'Szukam…' : 'Szukaj'}
            </button>
          </form>

          {bladSzukania && <div className="blad" style={{ marginTop: 8 }}>{bladSzukania}</div>}

          {wynikSzukania && !trwaSzukanie && (
            <div className="stos" style={{ gap: 8, marginTop: 10 }}>
              {wynikSzukania.wyniki.length === 0 ? (
                <div className="maly">
                  Brak wyników dla „{wynikSzukania.zapytanie}” w plikach: {wynikSzukania.dostepne_pliki.join(', ') || 'brak'}.
                </div>
              ) : (
                wynikSzukania.wyniki.map((frag) => {
                  const juzDodana = podstawy.includes(frag.etykieta);
                  return (
                    <KartaFragmentu
                      key={`sz-${frag.plik}-${frag.etykieta}-${frag.strona ?? ''}`}
                      fragment={frag}
                      onWstawDoPisma={onWstawDoPisma}
                      onDodajPodstawe={onDodajPodstawe && !juzDodana ? () => onDodajPodstawe(frag.etykieta) : undefined}
                      juzWPodstawach={juzDodana}
                    />
                  );
                })
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function KartaFragmentu({
  fragment,
  onWstawDoPisma,
  onDodajPodstawe,
  juzWPodstawach,
}: {
  fragment: FragmentPrzepisu;
  onWstawDoPisma?: (tekst: string) => void;
  onDodajPodstawe?: () => void;
  juzWPodstawach?: boolean;
}) {
  const [pokazPelny, setPokazPelny] = useState(false);
  const trescDoWyswietlenia = pokazPelny && fragment.pelny_artykul ? fragment.pelny_artykul : fragment.tresc;

  return (
    <div className="cytat-przepisu">
      <div className="cytat-meta">
        <strong>{fragment.etykieta}</strong>
        <span className="cytat-zrodlo">
          {fragment.plik}
          {fragment.strona ? `, str. ${fragment.strona}` : ''}
          {' · '}
          {OPIS_DOPASOWANIA[fragment.dopasowanie]}
        </span>
      </div>
      <div className="cytat-tresc">{trescDoWyswietlenia}</div>
      <div className="rzad" style={{ marginTop: 6, gap: 6 }}>
        {fragment.pelny_artykul && (
          <button type="button" className="maly-p" onClick={() => setPokazPelny((v) => !v)}>
            {pokazPelny ? 'Pokaż tylko ustęp' : 'Pokaż cały artykuł'}
          </button>
        )}
        {onDodajPodstawe && (
          <button type="button" className="maly-p" onClick={onDodajPodstawe}>
            Dodaj do podstaw prawnych
          </button>
        )}
        {juzWPodstawach && <span className="maly">✓ w podstawach prawnych</span>}
        {onWstawDoPisma && (
          <>
            <button
              type="button"
              className="maly-p"
              onClick={() => onWstawDoPisma(fragment.etykieta)}
            >
              Wstaw odwołanie
            </button>
            <button
              type="button"
              className="maly-p"
              onClick={() => onWstawDoPisma(`${fragment.etykieta}: „${fragment.tresc}”`)}
            >
              Wstaw cytat
            </button>
          </>
        )}
      </div>
    </div>
  );
}
