"""
Test bramki cytatów w skrócie sesji Rady.

Czyste funkcje, bez sieci i bez kosztów: `python -m scripts.test_council_summary`

Testujemy jedyny mechanizm, który stoi między skrótem a przypisaniem radnemu
zdania, którego nie powiedział. Prompt prosi model o dosłowność — to prośba.
`verify_against_transcript` to bramka i tylko ona się liczy.
"""
import sys

from src.ai.council_summary import (
    CouncilSummaryModel,
    Resolution,
    SessionPoint,
    split_sentences,
    verify_against_transcript,
)
from src.services.council_transcript import Segment, Transcript, normalize_quote

FAILURES: list = []


def check(label: str, got, expected) -> None:
    ok = got == expected
    print(f"  {'OK  ' if ok else 'BŁĄD'} {label}: {got!r}" + ("" if ok else f" (oczekiwano {expected!r})"))
    if not ok:
        FAILURES.append(label)


def transcript() -> Transcript:
    return Transcript(
        segments=[
            Segment(0, 12, "Otwieram dwudziestą trzecią sesję Rady Gminy Rybno."),
            Segment(600, 615, "Stawka za odbiór odpadów wzrośnie do trzydziestu dwóch złotych od osoby."),
            Segment(1800, 1815, "Przetarg na remont drogi w Hartowcu został rozstrzygnięty."),
            Segment(3600, 3620, "Uchwała została przyjęta jednogłośnie, piętnaście głosów za."),
        ],
        duration_s=5185.0,
    )


def test_normalizacja() -> None:
    print("\n== Normalizacja cytatu ==")
    check(
        "interpunkcja nie zmienia cytatu",
        normalize_quote("Uchwała została przyjęta, jednogłośnie!"),
        normalize_quote("uchwała została przyjęta jednogłośnie"),
    )
    check("puste wejście", normalize_quote(""), "")


def test_cytat_prawdziwy_zostaje() -> None:
    print("\n== Cytat obecny w nagraniu ==")
    tr = transcript()
    summary = CouncilSummaryModel(
        headline="Wyższa stawka za odpady",
        lead="Rada zdecydowała o podwyżce.",
        points=[
            SessionPoint(
                title="Podwyżka opłaty za odpady",
                description="Stawka rośnie do 32 zł od osoby.",
                timestamp="00:00:00",  # model podał zły znacznik
                quote="Stawka za odbiór odpadów wzrośnie do trzydziestu dwóch złotych od osoby.",
                speaker="Wójt",
            )
        ],
    )
    report = verify_against_transcript(summary, tr)

    check("cytat zachowany", summary.points[0].quote is not None, True)
    check("znacznik poprawiony na miejsce cytatu", summary.points[0].timestamp, "00:10:00")
    check("licznik poprawek", report.timestamps_fixed, 1)
    check("skuteczność cytatów", report.quote_accuracy, 1.0)
    check("nadaje się do publikacji", report.publishable, True)


def test_cytat_zmyslony_leci() -> None:
    print("\n== Cytat, którego nie było ==")
    tr = transcript()
    summary = CouncilSummaryModel(
        headline="Deklaracja wójta",
        lead="Padła obietnica.",
        points=[
            SessionPoint(
                title="Obietnica budowy hali",
                description="Zapowiedziano halę sportową.",
                timestamp="00:30:00",
                quote="Obiecuję, że hala sportowa powstanie do końca roku.",
                speaker="Wójt Tomasz Węgrzynowski",
            )
        ],
    )
    report = verify_against_transcript(summary, tr)

    check("cytat usunięty", summary.points[0].quote, None)
    check("mówca też usunięty", summary.points[0].speaker, None)
    check("punkt zachowany", len(summary.points), 1)
    check("zliczony jako odrzucony", len(report.quotes_dropped), 1)
    check("NIE nadaje się do publikacji", report.publishable, False)


def test_cytat_przez_dwa_segmenty() -> None:
    """
    Regresja z pilota 6.08.2026: Whisper tnie mowę co kilka sekund, więc cytat
    obejmujący dwa segmenty wyglądał na zmyślony. Bramka odrzuciła wtedy 3 z 4
    prawdziwych cytatów — fałszywy alarm jest tu równie groźny co przeoczenie,
    bo uczy ignorować ostrzeżenia.
    """
    print("\n== Cytat na styku dwóch segmentów ==")
    tr = Transcript(
        segments=[
            Segment(100, 106, "Za przyjęciem uchwały głosowało dwunastu radnych."),
            Segment(106, 112, "Nikt z radnych nie był przeciw."),
        ],
        duration_s=200.0,
    )
    summary = CouncilSummaryModel(
        headline="Uchwała przyjęta",
        lead="Głosowanie bez sprzeciwu.",
        points=[
            SessionPoint(
                title="Głosowanie",
                description="Uchwała przeszła.",
                timestamp="00:00:00",
                quote="Za przyjęciem uchwały głosowało dwunastu radnych. Nikt z radnych nie był przeciw.",
            )
        ],
    )
    report = verify_against_transcript(summary, tr)
    check("cytat przez granicę segmentów zachowany", summary.points[0].quote is not None, True)
    check("znacznik wskazuje początek cytatu", summary.points[0].timestamp, "00:01:40")
    check("brak fałszywego alarmu", report.quotes_dropped, [])


def test_parafraza_nie_przechodzi() -> None:
    print("\n== Parafraza to nie cytat ==")
    tr = transcript()
    summary = CouncilSummaryModel(
        headline="Odpady drożeją",
        lead="Podwyżka opłat.",
        points=[
            SessionPoint(
                title="Opłata za odpady",
                description="Stawka rośnie.",
                timestamp="00:10:00",
                # sens ten sam, słowa inne — dla mieszkańca to wciąż cudze słowa
                quote="Stawka za śmieci pójdzie w górę do 32 zł od mieszkańca.",
            )
        ],
    )
    report = verify_against_transcript(summary, tr)
    check("parafraza odrzucona", summary.points[0].quote, None)
    check("odnotowana w raporcie", len(report.quotes_dropped), 1)


def test_znacznik_poza_nagraniem() -> None:
    print("\n== Znacznik spoza nagrania ==")
    tr = transcript()  # 5185 s = 01:26:25
    summary = CouncilSummaryModel(
        headline="Punkt z przyszłości",
        lead="Model podał znacznik dłuższy niż nagranie.",
        points=[
            SessionPoint(title="Sprawa", description="Opis.", timestamp="03:00:00"),
        ],
        resolutions=[Resolution(subject="Uchwała budżetowa", timestamp="04:00:00")],
    )
    report = verify_against_transcript(summary, tr)

    check("znacznik punktu wyzerowany", summary.points[0].timestamp, "00:00:00")
    check("znacznik uchwały wyczyszczony", summary.resolutions[0].timestamp, None)
    check("policzone poza zakresem", report.timestamps_out_of_range, 2)
    check("NIE nadaje się do publikacji", report.publishable, False)


def test_podzial_na_zdania() -> None:
    """
    Jednostką weryfikacji opisu jest zdanie, więc zły podział psuje bramkę
    dwustronnie: urwany fragment nie ma pokrycia (fałszywy alarm), a sklejone
    zdania przepuszczają zmyślone twierdzenie razem z prawdziwym.
    """
    print("\n== Podział opisu na zdania ==")
    check(
        "kropka w kwocie nie kończy zdania",
        split_sentences("Rada zgodziła się na kredyt 500 tys. zł dla OSP. Spłata z dochodów własnych."),
        ["Rada zgodziła się na kredyt 500 tys. zł dla OSP.", "Spłata z dochodów własnych."],
    )
    check(
        "skrót art. nie kończy zdania",
        len(split_sentences("Podstawa to art. 18 ust. 2 ustawy o samorządzie gminnym.")),
        1,
    )
    check("puste wejście", split_sentences(""), [])
    check(
        "zdanie bez kropki na końcu też jest zdaniem",
        split_sentences("Uchwała przeszła jednogłośnie"),
        ["Uchwała przeszła jednogłośnie"],
    )


def test_brak_cytatow_jest_ok() -> None:
    print("\n== Skrót bez cytatów ==")
    tr = transcript()
    summary = CouncilSummaryModel(
        headline="Sesja bez cytatów",
        lead="Model nie podał żadnego cytatu — to poprawna odpowiedź.",
        points=[SessionPoint(title="Sprawa", description="Opis.", timestamp="00:10:00")],
    )
    report = verify_against_transcript(summary, tr)
    check("brak cytatów nie blokuje publikacji", report.publishable, True)
    check("skuteczność nieokreślona", report.quote_accuracy, None)


def main() -> int:
    print("=" * 68)
    print("BRAMKA CYTATÓW — skrót sesji Rady Gminy")
    print("=" * 68)
    test_normalizacja()
    test_cytat_prawdziwy_zostaje()
    test_cytat_zmyslony_leci()
    test_cytat_przez_dwa_segmenty()
    test_parafraza_nie_przechodzi()
    test_znacznik_poza_nagraniem()
    test_podzial_na_zdania()
    test_brak_cytatow_jest_ok()

    print("\n" + "=" * 68)
    if FAILURES:
        print(f"NIEPOWODZENIA ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("Wszystkie testy przeszły.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
