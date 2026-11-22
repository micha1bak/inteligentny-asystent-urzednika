# TC07 - BRAK WYDZIALU - ZDMiKP dysponentem (wskazanie dysponenta)

Żądane dane posiada miejska jednostka organizacyjna (ZDMiKP), a nie Urząd Miasta. Wniosku nie przekazuje się do wydziału – BKS od razu informuje wnioskodawcę o właściwym dysponencie (jak BKS.IV.1431.17.2026).

- Numer sprawy: `BKS.IV.1431.707.2026`, wpływ: 2026-11-12
- Wnioskodawca: Krzysztof Jankowski (zwrot: pan)
- Oczekiwany wydział: **brak** – dysponent poza UMB: Zarząd Dróg Miejskich i Komunikacji Publicznej w Bydgoszczy
- Niepoprawne wybory: WUK, WIM, WGK
- Werdykt: `NIE_MOZNA_PISMO_INFORMACYJNE`, wzór pisma: `nieposiadanie_wskazanie_dysponenta`

## Pliki

- `1_wniosek.docx`
- `2_oczekiwany_wydzial.json`
- `3_oczekiwana_wiadomosc_do_wydzialu.txt`
- `5_oczekiwana_odpowiedz_do_wnioskodawcy.txt`
- `5_oczekiwana_odpowiedz_do_wnioskodawcy.docx`
- `testcase.json`

## Kryteria oceny

- Brak wydziału UMB do wysłania prośby; aplikacja wskazuje podmiot_poza_umb = ZDMiKP.
- WUK (transport) NIE jest poprawnym wyborem – uprawnienia komunikacyjne to prawa jazdy i rejestracja pojazdów.
- Wzór: UMB nie jest dysponentem informacji – z danymi kontaktowymi ZDMiKP (jak w BKS.IV.1431.17.2026).
- Odpowiedź może być wysłana od razu, bez czekania na wydział (krótki czas obsługi).
