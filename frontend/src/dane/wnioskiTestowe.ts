import type { Status, Wniosek } from '../types';
import { dodajDni } from '../lib/daty';
import { czyDzienWolny, najblizszyRoboczy, terminOdpowiedzi } from '../lib/terminy';

/**
 * 10 fikcyjnych wniosków testowych. Daty wpływu liczone są względem dnia wczytania tak,
 * żeby w kalendarzu zawsze były sprawy po terminie, na dziś, na jutro i późniejsze.
 * Osoby i dane osobowe są zmyślone.
 */
interface Szablon {
  temat: string;
  terminZaDni: number;
  inicjaly: string;
  status: Status;
  wydzialy?: string[];
  dniKwerendy?: number;
  wnioskodawca: string;
  tresc: string;
  odpowiedz?: { wydzial: string; tresc: string };
}

const SZABLONY: Szablon[] = [
  {
    temat: 'Koszt remontu ul. Gdańskiej w 2026 r.', terminZaDni: -1, inicjaly: 'AK', status: 'zapytania_wyslane',
    wydzialy: ['WIM'], wnioskodawca: 'Jan Nowicki',
    tresc: 'Szanowni Państwo,\nna podstawie art. 2 ust. 1 ustawy o dostępie do informacji publicznej wnoszę o udostępnienie informacji o całkowitym koszcie remontu ul. Gdańskiej przeprowadzonego w 2026 r., z podziałem na etapy, oraz o nazwie wykonawcy.\nOdpowiedź proszę przesłać na adres e-mail: jan.nowicki@example.com\nZ poważaniem\nJan Nowicki',
    odpowiedz: { wydzial: 'WIM', tresc: 'W odpowiedzi na zapytanie BKS informujemy, że remont ul. Gdańskiej w 2026 r. kosztował łącznie 12 300 000 zł brutto: etap I – 5 100 000 zł, etap II – 7 200 000 zł. Wykonawcą była firma Drogbud Sp. z o.o. wybrana w przetargu nieograniczonym. Sprawę prowadzi inspektor Krzysztof Malinowski, tel. 601 222 333.' },
  },
  {
    temat: 'Wynagrodzenia kadry kierowniczej urzędu', terminZaDni: 0, inicjaly: 'AK', status: 'zapytania_wyslane',
    wydzialy: ['WOA'], wnioskodawca: 'Fundacja Przejrzyste Miasto',
    tresc: 'Fundacja Przejrzyste Miasto wnosi o udostępnienie informacji o wysokości wynagrodzeń (brutto, łącznie z nagrodami) Prezydenta Miasta, zastępców Prezydenta, Sekretarza i Skarbnika Miasta za rok 2025.\nOdpowiedź w formie elektronicznej na adres: biuro@przejrzyste-miasto.example.org',
  },
  {
    temat: 'Wycinka drzew przy ul. Fordońskiej', terminZaDni: 1, inicjaly: 'MW', status: 'brak_dzialan',
    wnioskodawca: 'Katarzyna Zielińska',
    tresc: 'Dzień dobry,\nproszę o informację, na jakiej podstawie wydano zgodę na wycinkę drzew przy ul. Fordońskiej w październiku 2026 r., ile drzew wycięto i jakie nasadzenia zastępcze zaplanowano.\nKatarzyna Zielińska, ul. Lipowa 7/3, 85-001 Bydgoszcz, tel. 600 123 456',
  },
  {
    temat: 'Wydatki na promocję miasta w mediach', terminZaDni: 1, inicjaly: 'MW', status: 'kwerenda', dniKwerendy: 14,
    wydzialy: ['BP', 'BPR'], wnioskodawca: 'Redakcja Gazety Bydgoskiej',
    tresc: 'Proszę o zestawienie umów zawartych przez Urząd Miasta Bydgoszczy w 2026 r. na promocję miasta w mediach (prasa, radio, telewizja, internet), z podaniem kontrahenta, przedmiotu i kwoty każdej umowy.',
  },
  {
    temat: 'Liczba uczniów w szkołach podstawowych', terminZaDni: 3, inicjaly: 'PB', status: 'zapytania_wyslane',
    wydzialy: ['WE'], wnioskodawca: 'Tomasz Lewandowski',
    tresc: 'Wnoszę o udostępnienie danych o liczbie uczniów w poszczególnych szkołach podstawowych prowadzonych przez Miasto Bydgoszcz w roku szkolnym 2026/2027 oraz o liczbie oddziałów w każdej szkole.',
    odpowiedz: { wydzial: 'WE', tresc: 'Wydział Edukacji i Sportu informuje, że w roku szkolnym 2026/2027 do szkół podstawowych prowadzonych przez Miasto uczęszcza 24 870 uczniów w 1 112 oddziałach. Dane dla poszczególnych szkół w załączonej tabeli.' },
  },
  {
    temat: 'Realizacja projektów budżetu obywatelskiego 2025', terminZaDni: 5, inicjaly: 'PB', status: 'brak_dzialan',
    wnioskodawca: 'Stowarzyszenie Aktywni Mieszkańcy',
    tresc: 'Prosimy o informację o stanie realizacji projektów wybranych w Bydgoskim Budżecie Obywatelskim na rok 2025: które projekty zostały zrealizowane, które są w trakcie i jaki jest ich koszt.',
  },
  {
    temat: 'Zaległości w podatku od nieruchomości', terminZaDni: 7, inicjaly: 'AK', status: 'brak_dzialan',
    wnioskodawca: 'Marek Wiśniewski',
    tresc: 'Proszę o informację o łącznej kwocie zaległości w podatku od nieruchomości na koniec 2025 r. oraz o kwocie umorzeń udzielonych w 2025 r. przedsiębiorcom.',
  },
  {
    temat: 'Pozwolenie na rozbudowę budynku sąsiada', terminZaDni: 9, inicjaly: 'MW', status: 'brak_dzialan',
    wnioskodawca: 'Aleksandra Wójcik-Nowak',
    tresc: 'Bydgoszcz, 12 listopada 2026 r.\n\nAleksandra Wójcik-Nowak\nul. Długa 15 m. 4\n85-034 Bydgoszcz\nPESEL: 44051401359\nseria i nr dowodu: ABC 123456\ntel. +48 601 234 567\ne-mail: a.wojcik.nowak@example.com\nnr rachunku: PL61 1090 1014 0000 0712 1981 2874\n\nWNIOSEK O UDOSTĘPNIENIE INFORMACJI PUBLICZNEJ\n\nNa podstawie art. 2 ust. 1 ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej wnoszę o udostępnienie informacji, czy mój sąsiad, pan Roman Kowalczyk zamieszkały przy ul. Długiej 17, otrzymał w 2026 r. pozwolenie na rozbudowę budynku, a jeśli tak – kiedy zostało wydane i jakie prace obejmuje.\n\nProszę również o informację, ile wniosków o pozwolenie na rozbudowę budynków jednorodzinnych na osiedlu Bocianowo wpłynęło w 2026 r.\n\nZ poważaniem\nAleksandra Wójcik-Nowak',
  },
  {
    temat: 'Diety radnych Rady Miasta', terminZaDni: 11, inicjaly: 'PB', status: 'odpowiedz_przygotowana',
    wydzialy: ['BRM'], wnioskodawca: 'Piotr Mazur',
    tresc: 'Proszę o informację o wysokości diet wypłaconych poszczególnym radnym Rady Miasta Bydgoszczy w 2025 r.',
    odpowiedz: { wydzial: 'BRM', tresc: 'Biuro Rady Miasta przekazuje zestawienie diet wypłaconych radnym w 2025 r. Łączna kwota diet wyniosła 1 845 000 zł. Wysokość diety miesięcznej określa uchwała nr XII/245/24 Rady Miasta Bydgoszczy. Zestawienie imienne w załączniku.' },
  },
  {
    temat: 'Liczba wydanych pozwoleń na budowę', terminZaDni: 13, inicjaly: 'AK', status: 'brak_dzialan',
    wnioskodawca: 'Ewa Dąbrowska',
    tresc: 'Proszę o podanie liczby pozwoleń na budowę budynków mieszkalnych wielorodzinnych wydanych przez Prezydenta Miasta Bydgoszczy w latach 2024–2026, z podziałem na lata.',
  },
];

/** Szuka daty wpływu, dla której termin (z kwerendą i przesunięciem na dzień roboczy) wypada najbliżej celu. */
function dataWplywuDlaTerminu(cel: string, dniKwerendy?: number): string {
  let najlepsza = dodajDni(cel, -14 - (dniKwerendy ?? 0));
  for (let przesuniecie = 0; przesuniecie < 10; przesuniecie++) {
    const kandydat = dodajDni(najlepsza, -przesuniecie);
    if (terminOdpowiedzi({ dataWplywu: kandydat, dniKwerendy }) === cel) return kandydat;
  }
  return najlepsza;
}

/** Przesunięcie o n dni roboczych (termin zawsze wypada w dzień roboczy, więc tak rozkładamy przykłady). */
function dodajDniRobocze(iso: string, n: number): string {
  let d = n >= 0 ? najblizszyRoboczy(iso) : iso;
  const krok = n >= 0 ? 1 : -1;
  for (let i = 0; i < Math.abs(n); i++) {
    d = dodajDni(d, krok);
    while (czyDzienWolny(d)) d = dodajDni(d, krok);
  }
  return d;
}

export function wnioskiTestowe(dzis: string): Wniosek[] {
  const rok = dzis.slice(0, 4);
  return SZABLONY.map((s, i) => {
    const dataWplywu = dataWplywuDlaTerminu(dodajDniRobocze(dzis, s.terminZaDni), s.dniKwerendy);
    const numer = `BKS.IV.1431.${601 + i}.${rok}`;
    return {
      id: `test-${i + 1}`,
      numer,
      dataWplywu,
      temat: s.temat,
      wnioskodawca: s.wnioskodawca,
      kontakt: s.tresc.match(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/)?.[0],
      inicjaly: s.inicjaly,
      tresc: s.tresc,
      status: s.status,
      dniKwerendy: s.dniKwerendy,
      wydzialy: s.wydzialy ?? [],
      odpowiedzi: s.odpowiedz
        ? [{ id: `odp-${i + 1}`, wydzial: s.odpowiedz.wydzial, tresc: s.odpowiedz.tresc, dodano: dataWplywu }]
        : [],
    };
  });
}
