"""
Test bramki akceptacji skrótu sesji Rady.

Czyste funkcje, bez sieci i bez bazy: `python -m scripts.test_council_store`

Bramka cytatów (`test_council_summary`) pilnuje, żeby model nie włożył radnemu
w usta cudzych słów. Ta bramka pilnuje czegoś innego: żeby **cokolwiek** wyszło
do ludzi dopiero po kliknięciu człowieka. Testujemy więc trzy rzeczy, których
złamanie oznacza publikację bez zgody:

1. skrót rodzi się w `pending`, nigdy w `published`,
2. token akceptacyjny jest jednorazowy i znika po decyzji,
3. transkrypt i token nie wyciekają publicznym payloadem.

Czwarta rzecz to znacznik: link `?t=` musi trafiać w tę samą sekundę, którą
zweryfikowała bramka cytatów — inaczej „sprawdź sam" jest pustą obietnicą.
"""
import sys

from src.ai.council_summary import (
    CouncilSummaryModel,
    CouncilSummaryResult,
    QualityReport,
    Resolution,
    SessionPoint,
)
from src.api.endpoints.council import _apply_decision
from src.database.schema import CouncilSession, CouncilSessionStatus
from src.services.council_store import (
    apply_result,
    flagged_claims,
    public_payload,
    render_review_page,
    summary_dict,
    transcript_from_json,
    transcript_to_json,
    watch_url,
)
from src.services.council_transcript import Segment, Transcript

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
            Segment(600, 615, "Stawka za odbiór odpadów wzrośnie do trzydziestu dwóch złotych."),
        ],
        duration_s=5185.0,
        source_url="https://www.youtube.com/watch?v=6h9iKlveTcs",
    )


def summary() -> CouncilSummaryModel:
    return CouncilSummaryModel(
        headline="Wyższa stawka za odpady",
        lead="Rada zdecydowała o podwyżce opłaty.",
        points=[
            SessionPoint(
                title="Podwyżka opłaty za odpady",
                description="Stawka rośnie do 32 zł od osoby.",
                timestamp="00:10:00",
                quote="Stawka za odbiór odpadów wzrośnie do trzydziestu dwóch złotych.",
            )
        ],
        resolutions=[Resolution(subject="Uchwała śmieciowa", number="XXIII/1/26", timestamp="00:20:00")],
    )


def row_pending() -> CouncilSession:
    """Wiersz po przebiegu joba — dokładnie to, co zobaczy strona akceptacji."""
    row = CouncilSession(
        external_id="7556",
        title="XXIII Sesja Rady Gminy Rybno z dnia 24.06.2026 r.",
        page_url="https://gminarybno.pl/nagrania_wideo/xxiii-sesja,7556.html",
        youtube_id="6h9iKlveTcs",
    )
    result = CouncilSummaryResult(
        summary=summary(),
        quality=QualityReport(
            quotes_total=1, quotes_verified=1, timestamps_fixed=1,
            claims_total=3,
            claims_flagged=["Działka ma być zagospodarowana na cele rekreacyjne."],
        ),
        tokens_input=40_000,
        tokens_output=1_200,
    )
    return apply_result(row, transcript(), result)


def test_transkrypt_wraca_bez_strat() -> None:
    print("\n== Transkrypt przez JSON i z powrotem ==")
    original = transcript()
    restored = transcript_from_json(transcript_to_json(original))

    check("liczba segmentów", len(restored.segments), len(original.segments))
    check("znacznik pierwszego segmentu", restored.segments[1].stamp, "00:10:00")
    check("długość nagrania", restored.duration_s, original.duration_s)
    # Bez tego cytatu nie da się już nigdy zweryfikować — a to jedyny powód,
    # dla którego transkrypt w ogóle trzymamy w bazie.
    check("cytat wciąż odnajdywalny",
          restored.locate("stawka za odbiór odpadów") is not None, True)


def test_skrot_rodzi_sie_do_akceptacji() -> None:
    print("\n== Stan początkowy skrótu ==")
    row = row_pending()

    check("status", row.status, CouncilSessionStatus.PENDING.value)
    check("NIE opublikowany", row.published_at, None)
    check("token wygenerowany", bool(row.review_token), True)
    check("token nietrywialny", len(row.review_token) >= 32, True)
    check("cytaty policzone", (row.quotes_verified, row.quotes_total), (1, 1))
    check("zdania opisów policzone", (row.claims_total, row.claims_flagged), (3, 1))
    # Wycięte zdanie musi dać się odczytać, nie tylko policzyć — inaczej admin
    # nie wie, w czym model konfabuluje.
    check("treść oznaczonego zdania zachowana",
          flagged_claims(row)[0].startswith("Działka"), True)
    # Jedno zdanie bez pokrycia wystarcza, by skrót NIE był czysty maszynowo.
    check("brak czystej bramki przy oznaczonym zdaniu", row.quotes_clean, False)
    check("transkrypt zapisany", row.transcript_chars > 0, True)
    # Whisper 5185 s = $0,5185 + gpt-4o (40k wejścia, 1,2k wyjścia) = $0,112.
    # Rachunek za sesję trzymamy w wierszu, bo bez niego nie wiadomo, ile
    # kosztuje odrzucony skrót — a odrzucony kosztuje dokładnie tyle samo.
    check("koszt policzony łącznie", row.cost_usd, 0.6305)


def test_znacznik_prowadzi_do_sekundy() -> None:
    print("\n== Link do minuty w nagraniu ==")
    row = row_pending()
    data = summary_dict(row)

    check("punkt ma link",
          data["points"][0]["watch_url"],
          "https://www.youtube.com/watch?v=6h9iKlveTcs&t=600s")
    check("uchwała też ma link",
          data["resolutions"][0]["watch_url"],
          "https://www.youtube.com/watch?v=6h9iKlveTcs&t=1200s")
    check("nagranie bez znacznika", watch_url(row),
          "https://www.youtube.com/watch?v=6h9iKlveTcs")

    # Sesja sprzed ery YouTube albo wpis bez iframe: brak linku jest poprawną
    # odpowiedzią, ale nie może wysypać renderowania strony.
    row.youtube_id = None
    check("brak nagrania nie wysypuje", watch_url(row, "00:10:00"), None)


def test_payload_nie_wynosi_transkryptu() -> None:
    print("\n== Co widzi świat ==")
    row = row_pending()
    payload = public_payload(row)
    flat = repr(payload)

    check("bez transkryptu", "transcript" in flat, False)
    check("bez tokenu akceptacyjnego", row.review_token in flat, False)
    check("jest nagłówek", payload["summary"]["headline"], "Wyższa stawka za odpady")
    check("jest długość nagrania", payload["duration_min"], 86)

    lekka = public_payload(row, with_summary=False)
    check("lista bez punktów", "summary" in lekka, False)


def test_decyzja_zuzywa_token() -> None:
    print("\n== Decyzja człowieka ==")
    row = row_pending()
    token = row.review_token

    _apply_decision(row, "publish", reviewed_by=1)
    check("status po publikacji", row.status, CouncilSessionStatus.PUBLISHED.value)
    check("data publikacji ustawiona", row.published_at is not None, True)
    check("kto zatwierdził", row.reviewed_by, 1)
    # Link krąży w skrzynce pocztowej — po użyciu nie może otwierać niczego,
    # co da się kliknąć drugi raz.
    check("token zużyty", row.review_token, None)
    check("token nie jest tym samym co był", row.review_token == token, False)

    odrzucony = row_pending()
    _apply_decision(odrzucony, "reject", reviewed_by=None)
    check("odrzucony status", odrzucony.status, CouncilSessionStatus.REJECTED.value)
    check("odrzucony nie ma daty publikacji", odrzucony.published_at, None)
    check("odrzucony token zużyty", odrzucony.review_token, None)


def test_strona_akceptacji() -> None:
    print("\n== Strona akceptacji ==")
    row = row_pending()
    page = render_review_page(row, action_url="/api/council/review/abc")

    check("oba przyciski są", ('value="publish"' in page, 'value="reject"' in page), (True, True))
    check("formularz idzie POST-em", 'method="post"' in page, True)
    check("widać listę do sprawdzenia", "Do sprawdzenia w nagraniu" in page, True)
    check("treść zmyślonego zdania na stronie", "cele rekreacyjne" in page, True)
    check("znacznik jest linkiem", "&t=600s" in page, True)
    check("cytat pokazany", "trzydziestu dwóch złotych" in page, True)

    # Tytuł sesji i treść punktów pochodzą z zewnątrz (galeria gminy + model),
    # więc idą przez `html.escape` — inaczej strona admina jest wektorem XSS.
    row.title = '<script>alert(1)</script>'
    escaped = render_review_page(row, action_url="/x")
    check("tytuł z galerii escapowany", "<script>" in escaped, False)


def main() -> int:
    print("=" * 68)
    print("BRAMKA AKCEPTACJI — skrót sesji Rady Gminy")
    print("=" * 68)
    test_transkrypt_wraca_bez_strat()
    test_skrot_rodzi_sie_do_akceptacji()
    test_znacznik_prowadzi_do_sekundy()
    test_payload_nie_wynosi_transkryptu()
    test_decyzja_zuzywa_token()
    test_strona_akceptacji()

    print("\n" + "=" * 68)
    if FAILURES:
        print(f"NIEPOWODZENIA ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("Wszystkie testy przeszły.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
