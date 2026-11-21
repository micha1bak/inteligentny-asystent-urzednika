// Proste wyszukiwanie semantyczne bez sieci: TF-IDF na "rdzeniach" słów (pierwsze 6 liter),
// co dla języka polskiego dobrze zbija odmiany (remontu/remont, drzew/drzewa).
// Docelowo do podmiany na embeddingi z lokalnego modelu po stronie backendu.

const STOP = new Set(
  'oraz które który która jakie jaki jaka przez proszę prosimy wnoszę wnosi informacji informację informacja udostępnienie udostępnienia dotyczy dotyczące roku latach miasta miasto bydgoszczy bydgoszcz urzędu urząd ustawy publicznej publiczną dostępie podstawie szanowni państwo poważaniem odpowiedź odpowiedzi będzie także również jeśli tylko można czy dnia wraz adres adresu mail przesłać przesłanie podziałem formie elektronicznej dzień dobry wniosek wniosku wniosków zakresie sprawie łącznie kwocie liczbie danych dane podanie zestawienie'.split(
    ' ',
  ),
);

export function rdzenie(tekst: string): string[] {
  const bezKontaktow = tekst.replace(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+|https?:\/\/\S+/g, ' ');
  return (bezKontaktow.toLowerCase().match(/\p{L}{4,}/gu) ?? [])
    .filter((s) => !STOP.has(s))
    .map((s) => s.slice(0, 6));
}

export interface Dokument<T> {
  element: T;
  tekst: string;
}

export interface Wynik<T> {
  element: T;
  wynik: number;
  wspolne: string[];
}

export function szukajPodobnych<T>(zapytanie: string, dokumenty: Dokument<T>[], limit = 5): Wynik<T>[] {
  const docs = dokumenty.map((d) => ({ d, tf: liczniki(rdzenie(d.tekst)) }));
  const df = new Map<string, number>();
  for (const { tf } of docs) for (const k of tf.keys()) df.set(k, (df.get(k) ?? 0) + 1);
  const n = docs.length + 1;
  const idf = (k: string) => Math.log(n / ((df.get(k) ?? 0) + 1)) + 1;
  const wektor = (tf: Map<string, number>) => {
    const w = new Map<string, number>();
    for (const [k, v] of tf) w.set(k, (1 + Math.log(v)) * idf(k));
    return w;
  };
  const q = wektor(liczniki(rdzenie(zapytanie)));
  const qNorm = norma(q);
  if (qNorm === 0) return [];
  return docs
    .map(({ d, tf }) => {
      const v = wektor(tf);
      let iloczyn = 0;
      const wspolne: string[] = [];
      for (const [k, x] of q) {
        const y = v.get(k);
        if (y) {
          iloczyn += x * y;
          wspolne.push(k);
        }
      }
      const vn = norma(v);
      return { element: d.element, wynik: vn ? iloczyn / (qNorm * vn) : 0, wspolne };
    })
    .filter((r) => r.wynik > 0.06)
    .sort((a, b) => b.wynik - a.wynik)
    .slice(0, limit);
}

function liczniki(tokeny: string[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const t of tokeny) m.set(t, (m.get(t) ?? 0) + 1);
  return m;
}

function norma(v: Map<string, number>): number {
  let s = 0;
  for (const x of v.values()) s += x * x;
  return Math.sqrt(s);
}
