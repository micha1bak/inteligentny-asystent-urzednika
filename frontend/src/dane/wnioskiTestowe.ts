import type { Wniosek } from '../types';
import { dodajDni } from '../lib/daty';
import { czyDzienWolny, najblizszyRoboczy, terminOdpowiedzi } from '../lib/terminy';

/**
 * 10 fikcyjnych wniosków testowych. Daty wpływu liczone są względem dnia wczytania tak, żeby najbliższy
 * termin wypadał dziś (żaden wniosek nie jest po terminie), a kolejne – jutro i w następnych dniach roboczych.
 * W dzień wolny „dziś” oznacza najbliższy dzień roboczy: termin z art. 13 UDIP nie może upłynąć w dzień wolny
 * (art. 57 § 4 KPA).
 * Wszystkie mają status „Brak działań” – urzędnik prowadzi je od początku.
 * Osoby i dane osobowe są zmyślone.
 */
interface Szablon {
  temat: string;
  terminZaDni: number;
  inicjaly: string;
  wnioskodawca: string;
  tresc: string;
}

const SZABLONY: Szablon[] = [
  {
    temat: 'Koszt remontu ul. Gdańskiej w 2026 r.', terminZaDni: 0, inicjaly: 'AK',
    wnioskodawca: 'Jan Nowicki',
    tresc: 'Szanowni Państwo,\nna podstawie art. 2 ust. 1 ustawy o dostępie do informacji publicznej wnoszę o udostępnienie informacji o całkowitym koszcie remontu ul. Gdańskiej przeprowadzonego w 2026 r., z podziałem na etapy, oraz o nazwie wykonawcy.\nOdpowiedź proszę przesłać na adres e-mail: jan.nowicki@example.com\nZ poważaniem\nJan Nowicki',
  },
  {
    temat: 'Wynagrodzenia kadry kierowniczej urzędu', terminZaDni: 0, inicjaly: 'AK',
    wnioskodawca: 'Fundacja Przejrzyste Miasto',
    tresc: 'Fundacja Przejrzyste Miasto wnosi o udostępnienie informacji o wysokości wynagrodzeń (brutto, łącznie z nagrodami) Prezydenta Miasta, zastępców Prezydenta, Sekretarza i Skarbnika Miasta za rok 2025.\nOdpowiedź w formie elektronicznej na adres: biuro@przejrzyste-miasto.example.org',
  },
  {
    temat: 'Wycinka drzew przy ul. Fordońskiej', terminZaDni: 1, inicjaly: 'MW',
    wnioskodawca: 'Katarzyna Zielińska',
    tresc: 'Dzień dobry,\nproszę o informację, na jakiej podstawie wydano zgodę na wycinkę drzew przy ul. Fordońskiej w październiku 2026 r., ile drzew wycięto i jakie nasadzenia zastępcze zaplanowano.\nKatarzyna Zielińska, ul. Lipowa 7/3, 85-001 Bydgoszcz, tel. 600 123 456',
  },
  {
    temat: 'Wydatki na promocję miasta w mediach', terminZaDni: 1, inicjaly: 'MW',
    wnioskodawca: 'Redakcja Gazety Bydgoskiej',
    tresc: 'Proszę o zestawienie umów zawartych przez Urząd Miasta Bydgoszczy w 2026 r. na promocję miasta w mediach (prasa, radio, telewizja, internet), z podaniem kontrahenta, przedmiotu i kwoty każdej umowy.',
  },
  {
    temat: 'Liczba uczniów w szkołach podstawowych', terminZaDni: 3, inicjaly: 'PB',
    wnioskodawca: 'Tomasz Lewandowski',
    tresc: 'Wnoszę o udostępnienie danych o liczbie uczniów w poszczególnych szkołach podstawowych prowadzonych przez Miasto Bydgoszcz w roku szkolnym 2026/2027 oraz o liczbie oddziałów w każdej szkole.',
  },
  {
    temat: 'Realizacja projektów budżetu obywatelskiego 2025', terminZaDni: 5, inicjaly: 'PB',
    wnioskodawca: 'Stowarzyszenie Aktywni Mieszkańcy',
    tresc: 'Prosimy o informację o stanie realizacji projektów wybranych w Bydgoskim Budżecie Obywatelskim na rok 2025: które projekty zostały zrealizowane, które są w trakcie i jaki jest ich koszt.',
  },
  {
    temat: 'Zaległości w podatku od nieruchomości', terminZaDni: 7, inicjaly: 'AK',
    wnioskodawca: 'Marek Wiśniewski',
    tresc: 'Proszę o informację o łącznej kwocie zaległości w podatku od nieruchomości na koniec 2025 r. oraz o kwocie umorzeń udzielonych w 2025 r. przedsiębiorcom.',
  },
  {
    temat: 'Pozwolenie na rozbudowę budynku sąsiada', terminZaDni: 9, inicjaly: 'MW',
    wnioskodawca: 'Aleksandra Wójcik-Nowak',
    tresc: 'Bydgoszcz, 12 listopada 2026 r.\n\nAleksandra Wójcik-Nowak\nul. Długa 15 m. 4\n85-034 Bydgoszcz\nPESEL: 44051401359\nseria i nr dowodu: ABC 123456\ntel. +48 601 234 567\ne-mail: a.wojcik.nowak@example.com\nnr rachunku: PL61 1090 1014 0000 0712 1981 2874\n\nWNIOSEK O UDOSTĘPNIENIE INFORMACJI PUBLICZNEJ\n\nNa podstawie art. 2 ust. 1 ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej wnoszę o udostępnienie informacji, czy mój sąsiad, pan Roman Kowalczyk zamieszkały przy ul. Długiej 17, otrzymał w 2026 r. pozwolenie na rozbudowę budynku, a jeśli tak – kiedy zostało wydane i jakie prace obejmuje.\n\nProszę również o informację, ile wniosków o pozwolenie na rozbudowę budynków jednorodzinnych na osiedlu Bocianowo wpłynęło w 2026 r.\n\nZ poważaniem\nAleksandra Wójcik-Nowak',
  },
  {
    temat: 'Diety radnych Rady Miasta', terminZaDni: 11, inicjaly: 'PB',
    wnioskodawca: 'Piotr Mazur',
    tresc: 'Proszę o informację o wysokości diet wypłaconych poszczególnym radnym Rady Miasta Bydgoszczy w 2025 r.',
  },
  {
    temat: 'Liczba wydanych pozwoleń na budowę', terminZaDni: 2, inicjaly: 'AK',
    wnioskodawca: 'Ewa Dąbrowska',
    tresc: 'Proszę o podanie liczby pozwoleń na budowę budynków mieszkalnych wielorodzinnych wydanych przez Prezydenta Miasta Bydgoszczy w latach 2024–2026, z podziałem na lata.',
  },
];

/** Szuka daty wpływu, dla której termin (z przesunięciem na dzień roboczy) wypada najbliżej celu. */
function dataWplywuDlaTerminu(cel: string): string {
  const najlepsza = dodajDni(cel, -14);
  for (let przesuniecie = 0; przesuniecie < 10; przesuniecie++) {
    const kandydat = dodajDni(najlepsza, -przesuniecie);
    if (terminOdpowiedzi({ dataWplywu: kandydat }) === cel) return kandydat;
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
    const wyliczona = dataWplywuDlaTerminu(dodajDniRobocze(dzis, s.terminZaDni));
    // wniosek nie może wpłynąć w przyszłości
    const dataWplywu = wyliczona > dzis ? dzis : wyliczona;
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
      status: 'brak_dzialan',
    };
  });
}
