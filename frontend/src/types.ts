import type { StrukturaPisma } from './lib/pismo';

export type Status =
  | 'brak_dzialan'
  | 'zapytania_wyslane'
  | 'kwerenda'
  | 'odpowiedz_przygotowana'
  | 'odpowiedz_wyslana';

export const STATUSY: { id: Status; etykieta: string }[] = [
  { id: 'brak_dzialan', etykieta: 'Nierozpatrzone' },
  { id: 'zapytania_wyslane', etykieta: 'Wysłane do wydziału' },
  { id: 'kwerenda', etykieta: 'Kwerenda' },
  { id: 'odpowiedz_przygotowana', etykieta: 'Odpowiedź przygotowana' },
  { id: 'odpowiedz_wyslana', etykieta: 'Rozpatrzone' },
];

export function etykietaStatusu(s: Status): string {
  return STATUSY.find((x) => x.id === s)?.etykieta ?? s;
}

export interface ZatwierdzonaOdpowiedz {
  werdykt: string;
  uzasadnienie: string;
  podstawyPrawne: string[];
  komorkaMerytoryczna: string;
  wzor: string;
  wzorNazwa: string;
  tresc: string;
  pismo: StrukturaPisma | null;
  autor: string;
  zatwierdzono: string;
}

export interface Wniosek {
  id: string;
  numer: string;
  dataWplywu: string; // YYYY-MM-DD
  temat: string;
  wnioskodawca: string;
  kontakt?: string;
  inicjaly: string;
  tresc: string;
  status: Status;
  /** Dodatkowe dni na odpowiedź (art. 13 ust. 2 UDIP), maks. do 2 miesięcy od wpływu. */
  dniKwerendy?: number;
  dataOdpowiedzi?: string; // YYYY-MM-DD
  nazwaPliku?: string;
  zatwierdzonaOdpowiedz?: ZatwierdzonaOdpowiedz;
  /** odpowiedzi komórek merytorycznych wgrane przez urzędnika (podstawa projektu pisma) */
  odpowiedziWydzialow?: OdpowiedzWydzialu[];
}

export interface OdpowiedzWydzialu {
  id: string;
  wydzial: string;
  nazwaPliku: string;
  tresc: string;
  dodano: string;
}
