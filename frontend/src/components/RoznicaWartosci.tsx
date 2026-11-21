/** Porównanie elementu bazy wiedzy przed i po zmianie – tylko pola, które się różnią. */

const NAZWY_POL: Record<string, string> = {
  nazwa: 'Nazwa',
  informacja: 'Informacja',
  zalozenia: 'Założenia',
  podstawa_prawna: 'Podstawa prawna',
  werdykt: 'Werdykt',
  nastepny_etap: 'Następny etap',
  kategoria: 'Kategoria',
  artykuly: 'Artykuły',
  zastosowanie: 'Zastosowanie',
  pelna_nazwa: 'Pełna nazwa',
  publikator: 'Publikator',
  skrot: 'Skrót',
  rozstrzygniecie: 'Rozstrzygnięcie',
  zasada_ogolna: 'Zasada ogólna',
};

function rowne(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function Wartosc({ v }: { v: unknown }) {
  if (v === undefined || v === null || v === '') return <span className="maly">—</span>;
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return <span>{String(v)}</span>;
  if (Array.isArray(v) && v.every((x) => typeof x === 'string')) {
    return (
      <ul className="lista-zwarta">
        {v.map((x, i) => <li key={i}>{x}</li>)}
      </ul>
    );
  }
  return <pre className="json">{JSON.stringify(v, null, 2)}</pre>;
}

function Pole({ nazwa, przed, po }: { nazwa?: string; przed: unknown; po: unknown }) {
  return (
    <div className="roznica-pole">
      {nazwa && <div className="roznica-nazwa">{nazwa}</div>}
      <div className="roznica-kolumny">
        <div className="roznica-przed">
          <div className="maly">Było</div>
          <Wartosc v={przed} />
        </div>
        <div className="roznica-po">
          <div className="maly">Będzie</div>
          <Wartosc v={po} />
        </div>
      </div>
    </div>
  );
}

export default function RoznicaWartosci({ przed, po }: { przed: unknown; po: unknown }) {
  const obiekty = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
  if (obiekty(przed) && obiekty(po)) {
    const klucze = [...new Set([...Object.keys(przed), ...Object.keys(po)])].filter((k) => !rowne(przed[k], po[k]));
    if (!klucze.length) return <p className="maly">Bez zmian treści.</p>;
    return (
      <>
        {klucze.map((k) =>
          obiekty(przed[k]) && obiekty(po[k]) ? (
            // zagnieżdżony obiekt (np. werdykt) – też tylko zmienione pola
            Object.keys({ ...(przed[k] as object), ...(po[k] as object) })
              .filter((kk) => !rowne((przed[k] as Record<string, unknown>)[kk], (po[k] as Record<string, unknown>)[kk]))
              .map((kk) => (
                <Pole
                  key={`${k}.${kk}`}
                  nazwa={`${NAZWY_POL[k] ?? k} › ${NAZWY_POL[kk] ?? kk}`}
                  przed={(przed[k] as Record<string, unknown>)[kk]}
                  po={(po[k] as Record<string, unknown>)[kk]}
                />
              ))
          ) : (
            <Pole key={k} nazwa={NAZWY_POL[k] ?? k} przed={przed[k]} po={po[k]} />
          ),
        )}
      </>
    );
  }
  return <Pole przed={przed} po={po} />;
}
