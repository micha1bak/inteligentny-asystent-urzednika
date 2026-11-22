"""100 przykładowych (FIKCYJNYCH) spraw do archiwum – więcej materiału do wyszukiwania podobnych spraw i przydziału
wniosków do wydziałów.

Sygnatury BKS.IV.1431.10.2025 – BKS.IV.1431.109.2025 (numeracja od 10, daty odpowiedzi styczeń–lipiec 2025);
numery 1–9 mają prawdziwe sprawy z archiwum. Tematy, liczby i kwoty są zmyślone, ale oddają typowe wnioski
do Urzędu Miasta Bydgoszczy i sposób ich załatwienia. Wpisy nie zawierają danych osobowych; każdy ma w historii
zmian adnotację, że jest przykładem.

Skrypt zapisuje też ten stan do archiwum_poczatkowe.json – przywraca go przycisk „Przywróć dane testowe”.

Uruchomienie (ponowne uruchomienie podmienia wcześniej wygenerowane wpisy, prawdziwych spraw nie rusza):
    uv run python skrypty/archiwum_przykladowe.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from inteligentny_asystent_urzednika import archiwum
from inteligentny_asystent_urzednika.config import wczytaj_ustawienia
from inteligentny_asystent_urzednika.wiedza import JEDNOSTKI_UMB, wczytaj_wiedze

PIERWSZY_NUMER = 10
ROK = 2025
AUTOR = "generator"
ADNOTACJA = "dodano (sprawa przykładowa, fikcyjna – skrypty/archiwum_przykladowe.py)"

U, A, W = "MOZNA_UDOSTEPNIC", "MOZNA_Z_ANONIMIZACJA", "MOZNA_WARUNKOWO"
D, M, P, B = "NIE_MOZNA_DECYZJA_ODMOWNA", "NIE_MOZNA_UMORZENIE_DECYZJA", "NIE_MOZNA_PISMO_INFORMACYJNE", "POZOSTAWIENIE_BEZ_ROZPOZNANIA"

FORMA = {
    U: "Pismo udostępniające informację (czynność materialno-techniczna)",
    A: "Pismo udostępniające informację po anonimizacji danych osobowych (czynność materialno-techniczna)",
    W: "Pismo wzywające wnioskodawcę (informacja przetworzona – wykazanie szczególnie istotnego interesu publicznego)",
    D: "Decyzja administracyjna o odmowie udostępnienia informacji publicznej",
    M: "Decyzja administracyjna o umorzeniu postępowania",
    P: "Zwykłe pismo informacyjne (bez wydawania decyzji administracyjnej)",
    B: "Pismo o pozostawieniu wniosku bez rozpoznania",
}
PODSTAWA = {
    U: "Art. 1 ust. 1, art. 6 ust. 1, art. 10 ust. 1 UDIP",
    A: "Art. 5 ust. 2, art. 10 ust. 1 UDIP",
    W: "Art. 3 ust. 1 pkt 1 UDIP",
    D: "Art. 16 ust. 1 w zw. z art. 5 ust. 2 UDIP",
    M: "Art. 14 ust. 2 UDIP",
    P: "Art. 4 ust. 3 UDIP",
    B: "Art. 64 § 2 KPA w zw. z art. 16 ust. 2 UDIP",
}
ZDMIKP = "Zarząd Dróg Miejskich i Komunikacji Publicznej w Bydgoszczy"


def s(wydzialy: str, werdykt: str, o_co: str, odpowiedz: str, podmiot: str = "", podstawa: str = "", forma: str = "") -> dict:
    return {"wydzialy": wydzialy.split(), "werdykt": werdykt, "wniosek_o_co": o_co, "jaka_odpowiedz": odpowiedz,
            "podmiot_poza_umb": podmiot, "etap_i_podstawa": podstawa or PODSTAWA[werdykt], "forma_zalatwienia": forma or FORMA[werdykt]}


SPRAWY = [
    # --- inwestycje i drogi
    s("WIM", U, "Koszt przebudowy ul. Grunwaldzkiej (etap I) w 2024 r., nazwa wykonawcy i planowany termin zakończenia robót.",
      "Udostępniono wartość umowy (18,4 mln zł brutto), nazwę wykonawcy wyłonionego w przetargu nieograniczonym i termin zakończenia robót (IV kwartał 2025 r.)."),
    s("WIM", U, "Wykaz remontów dróg gminnych wykonanych w 2024 r. wraz z kosztem każdego remontu.",
      "Udostępniono w załączniku zestawienie 23 zadań remontowych dróg gminnych o łącznej wartości 9,7 mln zł."),
    s("WIM WZP", U, "Budowa ronda na skrzyżowaniu ulic Fordońskiej i Toruńskiej: wykonawca, wartość umowy, aneksy i naliczone kary umowne.",
      "Udostępniono punkt po punkcie: wykonawcę, wartość umowy (6,2 mln zł), dwa aneksy wydłużające termin oraz kary umowne za zwłokę (84 tys. zł)."),
    s("WIM", U, "Koszt budowy drogi rowerowej wzdłuż ul. Kujawskiej i wysokość dofinansowania ze środków zewnętrznych.",
      "Udostępniono koszt inwestycji (2,1 mln zł) i kwotę dofinansowania z programu regionalnego (1,3 mln zł)."),
    s("WIM", A, "Kopie protokołów odbioru robót przy termomodernizacji budynku szkoły podstawowej.",
      "Udostępniono skany protokołów odbioru; zanonimizowano podpisy i dane osób fizycznych niepełniących funkcji publicznych."),
    s("", P, "Harmonogram remontu torowiska tramwajowego i nawierzchni jezdni na ul. Gdańskiej.",
      "Urząd Miasta nie posiada informacji – zadanie prowadzi miejska jednostka zarządzająca drogami; wskazano właściwy podmiot.",
      podmiot=ZDMIKP),
    s("WIM", W, "Zestawienie wszystkich inwestycji miejskich z ostatnich 10 lat z kosztami, opóźnieniami i aneksami do umów.",
      "Informacja wymaga przetworzenia (analiza kilkuset umów) – wezwano wnioskodawcę do wykazania szczególnie istotnego interesu publicznego."),
    s("WIM", U, "Koszt i zakres remontu nawierzchni oraz chodników na ul. Gdańskiej w 2024 r.",
      "Udostępniono wartość robót (3,6 mln zł), zakres (nawierzchnia jezdni, chodniki, przejścia dla pieszych) i nazwę wykonawcy."),
    # --- administracja budowlana
    s("WAB", A, "Kopia pozwolenia na budowę budynku wielorodzinnego przy ul. Szubińskiej wraz z projektem zagospodarowania terenu.",
      "Udostępniono decyzję i projekt zagospodarowania terenu; zanonimizowano dane inwestora będącego osobą fizyczną i projektanta."),
    s("WAB", U, "Liczba pozwoleń na budowę budynków mieszkalnych wielorodzinnych wydanych w latach 2022–2024 z podziałem na lata.",
      "Udostępniono liczby pozwoleń: 2022 r. – 41, 2023 r. – 37, 2024 r. – 45."),
    s("WAB", D, "Pełna dokumentacja projektowa (projekt techniczny) budynku biurowego realizowanego przez prywatnego inwestora.",
      "Odmówiono udostępnienia projektu technicznego ze względu na tajemnicę przedsiębiorcy zastrzeżoną przez inwestora; udostępniono decyzję o pozwoleniu na budowę."),
    s("", P, "Informacja, czy wszczęto postępowanie w sprawie samowoli budowlanej na sąsiedniej posesji.",
      "Urząd Miasta nie prowadzi postępowań w sprawie samowoli budowlanej; wskazano organ nadzoru budowlanego.",
      podmiot="Powiatowy Inspektor Nadzoru Budowlanego dla Miasta Bydgoszczy"),
    s("WAB", A, "Czy sąsiad otrzymał pozwolenie na rozbudowę domu jednorodzinnego, kiedy wydano decyzję i jakie prace obejmuje.",
      "Udostępniono datę wydania decyzji i zakres robót (rozbudowa o część mieszkalną); dane osobowe inwestora zanonimizowano."),
    s("WAB", U, "Liczba zgłoszeń robót budowlanych dotyczących instalacji fotowoltaicznych i pomp ciepła w 2024 r.",
      "Udostępniono liczbę zgłoszeń: 312 instalacji fotowoltaicznych i 97 pomp ciepła."),
    # --- edukacja i sport
    s("WE", U, "Liczba uczniów i oddziałów w poszczególnych szkołach podstawowych prowadzonych przez Miasto w roku szkolnym 2024/2025.",
      "Udostępniono w załączniku zestawienie dla 58 szkół podstawowych (łącznie ok. 27 tys. uczniów w 1230 oddziałach)."),
    s("WE", U, "Zestawienie przedszkoli miejskich: liczba dzieci, liczba oddziałów i liczba wolnych miejsc.",
      "Udostępniono w załączniku zestawienie 72 przedszkoli miejskich: liczbę dzieci, oddziałów i wolnych miejsc (łącznie 112)."),
    s("WE", U, "Wysokość wynagrodzeń dyrektorów szkół podstawowych prowadzonych przez Miasto w 2024 r.",
      "Udostępniono wysokość wynagrodzenia zasadniczego i dodatku funkcyjnego dyrektorów jako osób pełniących funkcje publiczne."),
    s("WE", U, "Wysokość dotacji dla klubów sportowych w 2024 r. z podziałem na kluby i dyscypliny.",
      "Udostępniono wykaz 34 klubów sportowych z kwotami dotacji (łącznie 6,8 mln zł) i dyscyplinami."),
    s("", P, "Średnie wyniki egzaminu ósmoklasisty w poszczególnych szkołach podstawowych w Bydgoszczy.",
      "Wyniki egzaminów opracowuje i publikuje komisja egzaminacyjna; Urząd nie jest dysponentem – wskazano właściwy podmiot.",
      podmiot="Okręgowa Komisja Egzaminacyjna w Gdańsku"),
    s("WE", A, "Kopie umów najmu sal gimnastycznych szkół podmiotom zewnętrznym w 2024 r.",
      "Udostępniono umowy; zanonimizowano dane najemców będących osobami fizycznymi."),
    s("WE", U, "Liczba nauczycieli zatrudnionych w szkołach miejskich i liczba wakatów na początku roku szkolnego.",
      "Udostępniono liczbę etatów nauczycielskich (4120) i liczbę nieobsadzonych stanowisk (86) z podziałem na typy szkół."),
    s("WE", U, "Liczba i wysokość stypendiów sportowych przyznanych przez Prezydenta Miasta w 2024 r.",
      "Udostępniono liczbę stypendiów (148) i łączną kwotę (512 tys. zł) bez danych stypendystów."),
    s("WE WIM", U, "Koszt remontu hali sportowej przy szkole podstawowej i termin oddania hali do użytku.",
      "Udostępniono koszt remontu (1,9 mln zł), zakres prac i termin oddania hali do użytku."),
    # --- odpady
    s("WGO", U, "Liczba złożonych deklaracji o wysokości opłaty za gospodarowanie odpadami komunalnymi i liczba zadeklarowanych mieszkańców.",
      "Udostępniono liczbę deklaracji (ok. 41 tys.) i liczbę mieszkańców wskazanych w deklaracjach (ok. 289 tys.)."),
    s("WGO", U, "Koszt systemu gospodarowania odpadami komunalnymi w 2024 r. i wysokość stawki opłaty dla mieszkańców.",
      "Udostępniono koszt systemu (98 mln zł), wpływy z opłat oraz stawkę opłaty od mieszkańca."),
    s("WGO", U, "Ilość odpadów przyjętych przez punkty selektywnej zbiórki odpadów komunalnych (PSZOK) w 2024 r.",
      "Udostępniono ilość przyjętych odpadów (ok. 6200 ton) z podziałem na frakcje."),
    s("WGO WW", U, "Kwota zaległości w opłatach za gospodarowanie odpadami i liczba wystawionych tytułów wykonawczych.",
      "Udostępniono kwotę zaległości (7,4 mln zł) i liczbę tytułów wykonawczych (ok. 3900)."),
    s("WGO", A, "Kopia umowy z firmą odbierającą odpady komunalne z nieruchomości zamieszkałych.",
      "Udostępniono umowę wraz z aneksami; zanonimizowano dane pracowników wykonawcy."),
    # --- podatki i opłaty lokalne
    s("WPL", U, "Łączna kwota zaległości w podatku od nieruchomości na koniec 2024 r.",
      "Udostępniono łączną kwotę zaległości (21,3 mln zł) z podziałem na osoby fizyczne i prawne, bez danych podatników."),
    s("WPL", U, "Kwota umorzeń w podatku od nieruchomości udzielonych przedsiębiorcom w 2024 r.",
      "Udostępniono łączną kwotę umorzeń (1,8 mln zł) i liczbę decyzji (142); wskazano wykaz publikowany w BIP na podstawie ustawy o finansach publicznych."),
    s("WPL", D, "Czy wskazany przedsiębiorca ma zaległości w podatku od nieruchomości i w jakiej wysokości.",
      "Odmówiono udostępnienia – informacja objęta tajemnicą skarbową (ograniczenie z art. 5 ust. 1 UDIP).",
      podstawa="Art. 16 ust. 1 w zw. z art. 5 ust. 1 UDIP; art. 293 Ordynacji podatkowej"),
    s("WPL", P, "Stawki podatku od nieruchomości obowiązujące w 2025 r.",
      "Poinformowano, że stawki określa uchwała Rady Miasta opublikowana w Biuletynie Informacji Publicznej i dzienniku urzędowym województwa.",
      podstawa="Art. 10 ust. 1 UDIP (informacja udostępniona w BIP)"),
    # --- organizacja urzędu
    s("WOA", U, "Wysokość wynagrodzeń (brutto, z nagrodami) Prezydenta Miasta, zastępców, Sekretarza i Skarbnika Miasta za 2024 r.",
      "Udostępniono roczne wynagrodzenia brutto osób pełniących funkcje publiczne wraz z nagrodami i dodatkami."),
    s("WOA", U, "Liczba samochodów służbowych Urzędu Miasta, wykaz marek i modeli oraz koszt paliwa w 2024 r.",
      "Udostępniono wykaz 27 pojazdów (marka, model, rok produkcji) i koszt paliwa (186 tys. zł)."),
    s("WOA", U, "Liczba pracowników Urzędu Miasta na koniec 2024 r. i przeciętne wynagrodzenie.",
      "Udostępniono liczbę etatów (ok. 1640) i przeciętne wynagrodzenie brutto w urzędzie."),
    s("WOA", D, "Kopia akt osobowych i ocen okresowych pracownika wydziału.",
      "Odmówiono udostępnienia – prywatność osoby fizycznej niepełniącej funkcji publicznej (art. 5 ust. 2 UDIP)."),
    s("WOA", U, "Łączna kwota nagród wypłaconych kadrze kierowniczej Urzędu Miasta w 2024 r.",
      "Udostępniono łączną kwotę nagród i liczbę nagrodzonych osób na stanowiskach kierowniczych."),
    s("WOA", P, "Aktualny regulamin organizacyjny Urzędu Miasta Bydgoszczy.",
      "Poinformowano, że regulamin organizacyjny jest opublikowany w Biuletynie Informacji Publicznej i wskazano adres strony.",
      podstawa="Art. 10 ust. 1 UDIP (informacja udostępniona w BIP)"),
    s("WOA", W, "Wszystkie umowy zlecenia i o dzieło zawarte przez Urząd Miasta w latach 2015–2024 z kwotami i przedmiotem umów.",
      "Informacja wymaga przetworzenia (kwerenda kilku tysięcy umów) – wezwano do wykazania szczególnie istotnego interesu publicznego."),
    # --- księgowość i budżet
    s("WK", U, "Wydatki Urzędu Miasta na obsługę prawną przez zewnętrzne kancelarie w 2024 r.",
      "Udostępniono wykaz płatności na rzecz kancelarii prawnych (łącznie 640 tys. zł) z nazwami kancelarii."),
    s("WZB", U, "Wysokość zadłużenia Miasta Bydgoszczy na koniec 2024 r. i prognoza na kolejne lata.",
      "Udostępniono kwotę zadłużenia i wskazano wieloletnią prognozę finansową."),
    s("WZB", U, "Planowane i wykonane wydatki inwestycyjne budżetu Miasta w 2024 r.",
      "Udostępniono plan i wykonanie wydatków majątkowych z podziałem na działy klasyfikacji budżetowej."),
    # --- mienie i geodezja
    s("WMG", U, "Wykaz nieruchomości miejskich sprzedanych w przetargach w 2024 r. z cenami sprzedaży.",
      "Udostępniono wykaz 31 nieruchomości z położeniem, powierzchnią i ceną uzyskaną w przetargu."),
    s("WMG", A, "Kopia umowy dzierżawy gruntu miejskiego wykorzystywanego jako parking.",
      "Udostępniono umowę dzierżawy; zanonimizowano dane dzierżawcy będącego osobą fizyczną."),
    s("WMG", U, "Liczba aktualizacji opłat za użytkowanie wieczyste w 2024 r. i wpływy z tych opłat.",
      "Udostępniono liczbę aktualizacji i roczne wpływy z opłat za użytkowanie wieczyste."),
    s("", P, "Kto jest właścicielem wskazanej działki i czy jest obciążona hipoteką.",
      "Poinformowano, że informacje zawiera księga wieczysta, dostępna w odrębnym trybie (art. 1 ust. 2 UDIP); wskazano wydział ksiąg wieczystych sądu.",
      podmiot="Sąd Rejonowy w Bydgoszczy – Wydział Ksiąg Wieczystych", podstawa="Art. 1 ust. 2 UDIP"),
    # --- ochrona środowiska
    s("WOŚ", A, "Zezwolenie na usunięcie drzew przy ul. Leśnej: liczba drzew, gatunki i nasadzenia zastępcze.",
      "Udostępniono decyzję (usunięcie 3 dębów, nasadzenia zastępcze 9 drzew); zanonimizowano dane wnioskodawcy – osoby fizycznej."),
    s("WOŚ", U, "Liczba zezwoleń na wycinkę drzew wydanych w 2024 r., liczba usuniętych drzew i nasadzeń zastępczych.",
      "Udostępniono liczbę zezwoleń (640), liczbę usuniętych drzew (ok. 2900) i nasadzeń zastępczych (ok. 3400)."),
    s("WOŚ", U, "Dotacje na wymianę źródeł ciepła (pieców węglowych) w 2024 r.: liczba i kwota.",
      "Udostępniono liczbę przyznanych dotacji (410) i łączną kwotę (4,1 mln zł)."),
    s("", P, "Wyniki pomiarów hałasu emitowanego przez zakład przemysłowy przy ul. Przemysłowej.",
      "Urząd nie posiada pomiarów hałasu tego zakładu; wskazano organ inspekcji ochrony środowiska.",
      podmiot="Wojewódzki Inspektorat Ochrony Środowiska w Bydgoszczy"),
    s("WOŚ", U, "Koszt programu kastracji i sterylizacji kotów wolno żyjących w 2024 r.",
      "Udostępniono liczbę zabiegów i łączny koszt programu."),
    s("WOŚ", A, "Kopia decyzji o środowiskowych uwarunkowaniach dla inwestycji magazynowej.",
      "Udostępniono decyzję; zanonimizowano dane osób fizycznych będących stronami postępowania."),
    # --- zieleń i gospodarka komunalna
    s("WGK", U, "Liczba drzew posadzonych przez Miasto w 2024 r. i koszt nasadzeń.",
      "Udostępniono liczbę nasadzonych drzew (ok. 1850) i koszt (2,3 mln zł)."),
    s("WGK", U, "Koszt utrzymania parków i zieleńców miejskich w 2024 r. oraz wykonawcy usług.",
      "Udostępniono koszt utrzymania zieleni z podziałem na rejony i nazwy wykonawców."),
    s("WGK", U, "Liczba psów i kotów przyjętych do schroniska dla zwierząt w 2024 r. i koszt opieki nad bezdomnymi zwierzętami.",
      "Udostępniono liczbę przyjętych zwierząt (910 psów, 610 kotów) i budżet schroniska (3,3 mln zł)."),
    s("WGK", U, "Koszt energii i konserwacji oświetlenia ulicznego oraz liczba punktów świetlnych w 2024 r.",
      "Udostępniono liczbę punktów świetlnych i koszty energii oraz konserwacji."),
    s("", P, "Liczba awarii sieci wodociągowej w 2024 r. i czas ich usuwania.",
      "Urząd Miasta nie posiada tych danych – sieć eksploatuje miejska spółka wodociągowa; wskazano właściwy podmiot.",
      podmiot="Miejskie Wodociągi i Kanalizacja w Bydgoszczy sp. z o.o."),
    # --- sprawy obywatelskie
    s("WSO", U, "Liczba dowodów osobistych wydanych przez Urząd Miasta w 2024 r.",
      "Udostępniono liczbę wydanych dowodów osobistych z podziałem na miesiące."),
    s("", P, "Przyczyny zamknięcia działalności gospodarczych przez przedsiębiorców z Bydgoszczy w 2024 r.",
      "Urząd nie prowadzi statystyk przyczyn zamknięcia działalności; rejestr CEIDG prowadzi minister właściwy do spraw gospodarki.",
      podmiot="Minister Rozwoju i Technologii (CEIDG)"),
    s("WSO", U, "Liczba zezwoleń na sprzedaż napojów alkoholowych i liczba punktów sprzedaży alkoholu w mieście.",
      "Udostępniono liczbę punktów sprzedaży (ok. 1140) i zezwoleń z podziałem na rodzaje."),
    s("WSO", P, "Adres zameldowania wskazanej osoby fizycznej.",
      "Poinformowano, że dane z rejestru mieszkańców udostępnia się w odrębnym trybie ustawy o ewidencji ludności, po wykazaniu interesu prawnego.",
      podstawa="Art. 1 ust. 2 UDIP"),
    s("WSO", U, "Liczba zgłoszonych zgromadzeń publicznych w 2024 r.",
      "Udostępniono liczbę zgłoszonych zgromadzeń (96) i liczbę zakazów zgromadzeń."),
    s("WSO", A, "Kopie zawiadomień o zgromadzeniach publicznych w centrum miasta w 2024 r.",
      "Udostępniono zawiadomienia; zanonimizowano dane organizatorów będących osobami fizycznymi."),
    # --- świadczenia rodzinne
    s("WSR", U, "Liczba osób pobierających świadczenia z funduszu alimentacyjnego i kwota wypłat w 2024 r.",
      "Udostępniono liczbę uprawnionych i łączną kwotę wypłaconych świadczeń."),
    s("WSR", D, "Czy wskazana osoba pobiera zasiłek rodzinny i w jakiej wysokości.",
      "Odmówiono udostępnienia – prywatność osoby fizycznej (art. 5 ust. 2 UDIP)."),
    # --- uprawnienia komunikacyjne
    s("WUK", U, "Liczba zarejestrowanych w mieście samochodów elektrycznych na koniec 2024 r.",
      "Udostępniono liczbę zarejestrowanych pojazdów elektrycznych i hybrydowych."),
    s("", P, "Zdawalność egzaminów na prawo jazdy kategorii B w Bydgoszczy.",
      "Urząd nie przeprowadza egzaminów; wskazano ośrodek egzaminowania.",
      podmiot="Wojewódzki Ośrodek Ruchu Drogowego w Bydgoszczy"),
    s("WUK", P, "Dane właściciela pojazdu o wskazanym numerze rejestracyjnym.",
      "Poinformowano, że dane z centralnej ewidencji pojazdów udostępnia się w odrębnym trybie ustawy Prawo o ruchu drogowym.",
      podstawa="Art. 1 ust. 2 UDIP"),
    # --- windykacja i zamówienia
    s("WW", U, "Łączna kwota należności Miasta dochodzonych w postępowaniach egzekucyjnych w 2024 r.",
      "Udostępniono łączną kwotę należności skierowanych do egzekucji i kwotę wyegzekwowaną."),
    s("WZP", U, "Przetargi na usługi sprzątania budynków Urzędu w 2024 r.: oferty i ceny.",
      "Udostępniono informacje z otwarcia ofert: wykonawców i zaoferowane ceny."),
    s("WZP", A, "Oferty złożone w przetargu na dostawę sprzętu komputerowego dla szkół.",
      "Udostępniono oferty z wyłączeniem części zastrzeżonych przez wykonawców jako tajemnica przedsiębiorstwa."),
    s("WZP", U, "Umowy na usługi doradcze i eksperckie zawarte przez Urząd w 2024 r. z wartościami.",
      "Udostępniono wykaz umów: wykonawca, przedmiot i wartość."),
    # --- zarządzanie kryzysowe, informatyka, fundusze
    s("WZK", D, "Wykaz i lokalizacja schronów oraz budowli ochronnych na terenie miasta wraz z ich stanem technicznym.",
      "Odmówiono udostępnienia w zakresie objętym ochroną informacji niejawnych; poinformowano o publicznie dostępnych miejscach doraźnego schronienia.",
      podstawa="Art. 16 ust. 1 w zw. z art. 5 ust. 1 UDIP"),
    s("WI", U, "Koszt licencji oprogramowania biurowego i systemów dziedzinowych Urzędu w 2024 r.",
      "Udostępniono łączny koszt licencji z podziałem na rodzaje oprogramowania."),
    s("WI", D, "Szczegółowa konfiguracja sieci komputerowej i zabezpieczeń systemów informatycznych Urzędu.",
      "Odmówiono udostępnienia ze względu na bezpieczeństwo systemów teleinformatycznych (tajemnica prawnie chroniona).",
      podstawa="Art. 16 ust. 1 w zw. z art. 5 ust. 1 UDIP"),
    s("WF", U, "Projekty Miasta dofinansowane ze środków Unii Europejskiej w perspektywie 2021–2027 i kwoty dofinansowania.",
      "Udostępniono wykaz projektów z wartością i kwotą dofinansowania."),
    s("BZIT", U, "Projekty realizowane w ramach Zintegrowanych Inwestycji Terytorialnych obszaru metropolitalnego.",
      "Udostępniono listę projektów ZIT z beneficjentami i stanem realizacji."),
    # --- biura
    s("BAS", U, "Stan realizacji projektów wybranych w Bydgoskim Budżecie Obywatelskim na 2024 r. i ich koszt.",
      "Udostępniono wykaz projektów ze statusem (zrealizowany, w trakcie, niezrealizowany) i kosztem."),
    s("BAS", U, "Dotacje dla organizacji pozarządowych w otwartych konkursach ofert w 2024 r.",
      "Udostępniono wykaz organizacji, zadań i kwot dotacji."),
    s("BAS", A, "Listy poparcia projektów zgłoszonych do budżetu obywatelskiego.",
      "Udostępniono listy poparcia po zanonimizowaniu danych osobowych mieszkańców (imion, nazwisk, adresów, podpisów)."),
    s("BCB", U, "Liczba naruszeń ochrony danych osobowych zgłoszonych przez Urząd organowi nadzorczemu w 2024 r.",
      "Udostępniono liczbę zgłoszonych naruszeń i ich rodzaje."),
    s("BZS", U, "Wydatki Miasta na program szczepień przeciw HPV i liczba zaszczepionych osób w 2024 r.",
      "Udostępniono koszt programu i liczbę wykonanych szczepień."),
    s("", P, "Liczba osób korzystających z zasiłków z pomocy społecznej w 2024 r.",
      "Urząd Miasta nie jest dysponentem – świadczenia przyznaje miejski ośrodek pomocy społecznej; wskazano właściwy podmiot.",
      podmiot="Miejski Ośrodek Pomocy Społecznej w Bydgoszczy"),
    s("BKZ", U, "Dotacje Miasta na prace konserwatorskie przy zabytkach w 2024 r.",
      "Udostępniono wykaz obiektów objętych dotacją, zakres prac i kwoty."),
    s("", P, "Czy kamienica przy ul. Gdańskiej jest wpisana do rejestru zabytków i od kiedy.",
      "Rejestr zabytków prowadzi wojewódzki konserwator zabytków; wskazano właściwy podmiot.",
      podmiot="Kujawsko-Pomorski Wojewódzki Konserwator Zabytków – Delegatura w Bydgoszczy"),
    s("BKB", U, "Dotacje podmiotowe dla miejskich instytucji kultury w 2024 r.",
      "Udostępniono kwoty dotacji dla poszczególnych instytucji kultury."),
    s("BKB", U, "Koszt organizacji festiwalu i wydarzeń z okazji Dni Bydgoszczy oraz wykonawcy.",
      "Udostępniono łączny koszt wydarzeń i wykaz umów z wykonawcami."),
    s("BPR", U, "Umowy zawarte przez Urząd w 2024 r. na promocję miasta w mediach (prasa, radio, telewizja, internet): kontrahent, przedmiot, kwota.",
      "Udostępniono zestawienie umów medialnych z kontrahentami, przedmiotem i kwotami."),
    s("BP", U, "Koszt kampanii promocyjnej miasta i wyjazdów do miast partnerskich w 2024 r.",
      "Udostępniono koszt kampanii i wykaz wyjazdów z kosztami."),
    s("BRM", U, "Wysokość diet wypłaconych poszczególnym radnym Rady Miasta w 2024 r.",
      "Udostępniono wysokość diet poszczególnych radnych (osoby pełniące funkcje publiczne)."),
    s("", P, "Udostępnienie nagrania z sesji Rady Miasta.",
      "Poinformowano, że nagrania sesji są udostępnione w Biuletynie Informacji Publicznej Rady Miasta.",
      podstawa="Art. 10 ust. 1 UDIP (informacja udostępniona w BIP)"),
    # --- sprawy nietypowe: brak dysponenta, inny tryb, braki formalne
    s("", P, "Punktualność kursów linii autobusowej i liczba opóźnionych kursów w 2024 r.",
      "Urząd Miasta nie posiada danych o punktualności komunikacji miejskiej; wskazano właściwą jednostkę.",
      podmiot=ZDMIKP),
    s("", P, "Wynagrodzenia kierowców autobusów i tramwajów komunikacji miejskiej.",
      "Urząd nie jest pracodawcą kierowców; wskazano miejską spółkę przewozową jako dysponenta informacji.",
      podmiot="Miejskie Zakłady Komunikacyjne sp. z o.o. w Bydgoszczy"),
    s("", W, "Wniosek o „wszystkie dokumenty w mojej sprawie” bez wskazania, o jaką sprawę chodzi.",
      "Wezwano wnioskodawcę do doprecyzowania wniosku (wskazania sprawy i rodzaju dokumentów).",
      forma="Pismo wzywające do doprecyzowania wniosku", podstawa="Art. 2 ust. 1, art. 10 ust. 1 UDIP"),
    s("", P, "Prośba o poradę prawną w sporze sąsiedzkim i udostępnienie danych kontaktowych sąsiada.",
      "Poinformowano, że porada prawna i dane osobowe sąsiada nie są informacją publiczną; wskazano bezpłatną pomoc prawną.",
      podstawa="Art. 1 ust. 1, art. 6 UDIP (żądanie nie dotyczy informacji publicznej)"),
    s("", P, "Skarga na sposób obsługi w wydziale połączona z żądaniem informacji o ukaraniu pracownika.",
      "Poinformowano, że skarga podlega rozpatrzeniu w trybie działu VIII KPA, a informacja o odpowiedzialności służbowej pracownika nie jest informacją publiczną.",
      podstawa="Art. 1 ust. 2 UDIP; art. 227 KPA"),
    s("WOA", M, "Kopie nagrań z monitoringu wizyjnego budynku Urzędu na wskazanym nośniku.",
      "Powiadomiono o braku możliwości udostępnienia w żądanej formie i wskazano inną formę; wnioskodawca nie odpowiedział w terminie 14 dni – postępowanie umorzono."),
    s("WMG", M, "Mapy zasobu nieruchomości miejskich w nietypowym formacie pliku wskazanym przez wnioskodawcę.",
      "Powiadomiono, że udostępnienie w żądanym formacie nie jest możliwe; brak odpowiedzi wnioskodawcy w terminie – umorzenie postępowania."),
    s("WIM", B, "Wniosek o udostępnienie umów inwestycyjnych, w sprawie zakończonej decyzją, bez podpisu wnioskodawcy.",
      "Wnioskodawca nie usunął braku formalnego (podpisu) w wyznaczonym terminie – wniosek pozostawiono bez rozpoznania."),
    s("WAB", B, "Odwołanie od odmowy udostępnienia dokumentacji budowlanej złożone bez danych umożliwiających doręczenie.",
      "Wnioskodawca nie uzupełnił adresu do doręczeń mimo wezwania – wniosek pozostawiono bez rozpoznania."),
]


def _komorka(sprawa: dict) -> str:
    if not sprawa["wydzialy"]:
        return "Biuro Komunikacji Społecznej (Urząd nie przekazał wniosku do wydziału)"
    nazwy = {j["symbol"]: j["nazwa"] for j in JEDNOSTKI_UMB}
    return nazwy[sprawa["wydzialy"][0]]


def _dzien_roboczy(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def wygeneruj() -> list[dict]:
    if len(SPRAWY) != 100:
        raise SystemExit(f"Oczekiwano 100 spraw, jest {len(SPRAWY)}.")
    poczatek = date(ROK, 1, 13)
    wynik = []
    for i, sprawa in enumerate(SPRAWY):
        wplyw = poczatek + timedelta(days=int(i * 1.7))
        odpowiedz = _dzien_roboczy(wplyw + timedelta(days=11 + i % 3))
        wynik.append({
            "sygnatura": f"BKS.IV.1431.{PIERWSZY_NUMER + i}.{ROK}",
            "data_odpowiedzi": odpowiedz.isoformat(),
            "komorka_merytoryczna": _komorka(sprawa),
            **sprawa,
        })
    return wynik


def main() -> None:
    u = wczytaj_ustawienia()
    plik: Path = u.plik_werdyktow
    slownik = wczytaj_wiedze(u.plik_oceny, plik, u.plik_wzorow).slownik_werdyktow
    nowe = wygeneruj()

    # walidacja jak przy zapisie z aplikacji: werdykt ze słownika, jednostki UMB, brak danych osobowych
    sprawy = [archiwum.Sprawa.model_validate(s) for s in nowe]
    for sprawa in sprawy:
        archiwum.sprawdz(sprawa, slownik)

    dane = archiwum.wczytaj(plik)
    generowane = {s.sygnatura for s in sprawy}
    prawdziwe = [s for s in dane["sprawy"] if s["sygnatura"] not in generowane]
    kiedy = f"{date.today().isoformat()}T00:00:00"
    dane["sprawy"] = prawdziwe + [
        {**s.model_dump(exclude={"nieaktualna"}), "historia": [{"kiedy": kiedy, "kto": AUTOR, "zmiana": ADNOTACJA, "pola": {}}]}
        for s in sprawy
    ]
    dane["metadane"]["sprawy_przykladowe"] = (
        f"BKS.IV.1431.{PIERWSZY_NUMER}.{ROK}–BKS.IV.1431.{PIERWSZY_NUMER + len(sprawy) - 1}.{ROK}: "
        "sprawy fikcyjne wygenerowane skryptem skrypty/archiwum_przykladowe.py (do testów wyszukiwania podobnych spraw)"
    )
    archiwum._zapisz(plik, dane)
    # ten sam stan jako początkowy – przywracany przyciskiem „Przywróć dane testowe”
    archiwum._zapisz(u.plik_archiwum_poczatkowego, json.loads(json.dumps(dane)))
    print(f"Zapisano {len(sprawy)} spraw przykładowych; w archiwum jest {len(dane['sprawy'])} spraw.", file=sys.stderr)


if __name__ == "__main__":
    main()
