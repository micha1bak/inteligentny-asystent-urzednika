export type Status =
  | 'brak_dzialan'
  | 'zapytania_wyslane'
  | 'kwerenda'
  | 'odpowiedz_przygotowana'
  | 'odpowiedz_wyslana';

export const STATUSY: { id: Status; etykieta: string }[] = [
  { id: 'brak_dzialan', etykieta: 'Brak działań' },
  { id: 'zapytania_wyslane', etykieta: 'Zapytania do wydziałów' },
  { id: 'kwerenda', etykieta: 'Kwerenda' },
  { id: 'odpowiedz_przygotowana', etykieta: 'Odpowiedź przygotowana' },
  { id: 'odpowiedz_wyslana', etykieta: 'Odpowiedź wysłana' },
];

export function etykietaStatusu(s: Status): string {
  return STATUSY.find((x) => x.id === s)?.etykieta ?? s;
}

/** Fragment tekstu do anonimizacji: [start, koniec) w znakach. */
export interface Fragment {
  id: string;
  start: number;
  koniec: number;
  kategoria: string;
  /** propozycja = szary (do decyzji), zaakceptowany = czarny, odrzucony = bez zmian */
  stan: 'propozycja' | 'zaakceptowany' | 'odrzucony';
  zrodlo: 'automat' | 'reczny';
}

export interface OdpowiedzWydzialu {
  id: string;
  wydzial: string;
  nazwaPliku?: string;
  tresc: string;
  dodano: string; // ISO
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
  wydzialy: string[]; // symbole jednostek, do których wysłano zapytanie
  odpowiedzi: OdpowiedzWydzialu[];
  projektPisma?: string;
  fragmenty?: Fragment[];
  werdykt?: string;
  ocenaEtapy?: Record<string, boolean>;
  dataOdpowiedzi?: string; // YYYY-MM-DD
  nazwaPliku?: string;
}

export interface SprawaArchiwalna {
  id: string;
  sygnatura: string;
  data: string;
  wniosek: string;
  odpowiedz: string;
  komorka: string;
  werdykt?: string;
  zrodlo: 'archiwum' | 'dodane';
}

export interface DokumentBazy {
  id: string;
  nazwa: string;
  rodzaj: 'ustawa' | 'zarzadzenie' | 'inne';
  dodano: string;
  znaki: number;
  tresc: string;
}

export interface Jednostka {
  symbol: string;
  rodzaj: string;
  nazwa: string;
  zakres: string;
}
