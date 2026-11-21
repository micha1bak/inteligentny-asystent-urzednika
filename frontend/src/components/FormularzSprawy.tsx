import type { Sprawa } from '../lib/api';

interface Props {
  sprawa: Sprawa;
  onZmiana: (s: Sprawa) => void;
  werdykty: Record<string, string>;
  jednostki: string[];
  /** przy edycji sygnatury nie można zmienić (to klucz wpisu) */
  sygnaturaStala?: boolean;
}

/** Pola wpisu archiwalnego – wspólne dla dodawania i edycji. */
export default function FormularzSprawy({ sprawa, onZmiana, werdykty, jednostki, sygnaturaStala }: Props) {
  const ustaw = (k: keyof Sprawa, v: string) => onZmiana({ ...sprawa, [k]: v });
  const opisWerdyktu = werdykty[sprawa.werdykt];

  return (
    <div className="formularz">
      <label>
        Sygnatura sprawy
        <input
          value={sprawa.sygnatura}
          disabled={sygnaturaStala}
          placeholder="BKS.IV.1431.N.RRRR"
          onChange={(e) => ustaw('sygnatura', e.target.value)}
        />
      </label>
      <label>
        Data odpowiedzi
        <input type="date" value={sprawa.data_odpowiedzi} onChange={(e) => ustaw('data_odpowiedzi', e.target.value)} />
      </label>
      <label className="pelny">
        Komórka merytoryczna
        <input
          list="jednostki-umb"
          value={sprawa.komorka_merytoryczna}
          onChange={(e) => ustaw('komorka_merytoryczna', e.target.value)}
          placeholder="np. Wydział Inwestycji Miasta"
        />
        <datalist id="jednostki-umb">
          {jednostki.map((j) => <option key={j} value={j} />)}
        </datalist>
      </label>
      <label className="pelny">
        Czego dotyczył wniosek
        <textarea rows={3} value={sprawa.wniosek_o_co} onChange={(e) => ustaw('wniosek_o_co', e.target.value)} />
      </label>
      <label className="pelny">
        Jaka była odpowiedź
        <textarea rows={4} value={sprawa.jaka_odpowiedz} onChange={(e) => ustaw('jaka_odpowiedz', e.target.value)} />
      </label>
      <label className="pelny">
        Werdykt
        <select value={sprawa.werdykt} onChange={(e) => ustaw('werdykt', e.target.value)}>
          <option value="">— wybierz —</option>
          {Object.keys(werdykty).map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        {opisWerdyktu && <span>{opisWerdyktu}</span>}
      </label>
      <label className="pelny">
        Forma załatwienia
        <input value={sprawa.forma_zalatwienia} onChange={(e) => ustaw('forma_zalatwienia', e.target.value)} placeholder="np. Pismo udostępniające informację" />
      </label>
      <label className="pelny">
        Etap oceny i podstawa prawna
        <input value={sprawa.etap_i_podstawa} onChange={(e) => ustaw('etap_i_podstawa', e.target.value)} placeholder="np. Art. 1 ust. 1, art. 10 ust. 1 UDIP" />
      </label>
    </div>
  );
}

/** Proste sprawdzenie przed wysłaniem (pełna walidacja, w tym danych osobowych, jest w backendzie). */
export function brakujacePola(s: Sprawa): string[] {
  const braki: string[] = [];
  if (s.sygnatura.trim().length < 3) braki.push('sygnatura');
  if (s.wniosek_o_co.trim().length < 10) braki.push('czego dotyczył wniosek');
  if (s.jaka_odpowiedz.trim().length < 10) braki.push('jaka była odpowiedź');
  if (!s.werdykt) braki.push('werdykt');
  return braki;
}
