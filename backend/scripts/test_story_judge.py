"""
Sędzia sprawy (audyt 11.10.2026, E3c).

Bez bazy i modelu (CI):
  1. wspólny `story_id` = ta sama sprawa, także gdy osie milczą; różne sprawy nie
  2. kandydaci do sędziego: weta osi PRZED sędzią, tylko starsze wpisy, próg 0,70,
     limit 5 na wpis, pary zwinięte już przez osie pomijane
Z bazą (`--db`, LOKALNA, zmiany wycofywane):
  3. `link_new_stories` z atrapą sędziego — korzeń sprawy, znacznik, błąd modelu
Z modelem (`--live`, ~2 grosze):
  4. 38 ręcznie ocenionych par (`fixtures/story_judge_pairs.json`):
     **0 sklejonych par „inna”** (warunek konieczny), zwinięte ≥ 85% par „ta_sama”/„odslona”.
     Uruchomić przed KAŻDĄ zmianą promptu albo obcinania treści.

    cd backend && python -m scripts.test_story_judge [--db] [--live]
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services import story_judge as sj
from src.services.feed_policy import same_story, story_key

results: list[bool] = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))


T0 = datetime(2026, 10, 8, 10, 0)


def art(id, title, content="", published_h=0.0, event_at=None, story_id=None):
    return SimpleNamespace(id=id, title=title, display_title=title, content=content, summary=None,
                           event_at=event_at, event_until=None, story_id=story_id,
                           published_at=T0 + timedelta(hours=published_h))


def vec(*head):
    return list(head) + [0.0] * (10 - len(head))


def section_story_axis() -> None:
    print("\n1️⃣  Wspólna sprawa w kluczu")
    a = art(1, "Dekorglass przegrał z Orliczem", "Działdowo", story_id=1)
    b = art(2, "Ranny policjant w aptece", "Lidzbark", story_id=1)
    check("wspólny story_id = ta sama sprawa, nawet przy zupełnie innych słowach",
          same_story(story_key(a), story_key(b)))
    c = art(3, "Ranny policjant w aptece", "Lidzbark", story_id=3)
    check("różne story_id nie skleja", not same_story(story_key(a), story_key(c)))
    d = art(4, "Dekorglass przegrał z Orliczem", "Działdowo")
    check("brak story_id — zwykłe osie jak dotąd", same_story(story_key(a), story_key(d)))


def section_candidates() -> None:
    print("\n2️⃣  Kto trafia do sędziego")
    new = art(10, "Wyłączenie prądu — Turza Mała", "Energa", published_h=5)
    old_far = art(11, "Wyłączenie prądu — Dwukoły", "Energa", published_h=1)
    old_low = art(12, "Kino w Lubawie", "", published_h=1)
    newer = art(13, "Wyłączenie prądu — Prioma", "Energa", published_h=8)
    too_old = art(14, "Wyłączenie prądu — Wysoka", "Energa", published_h=-100)
    other_day = art(15, "Zebranie wiejskie", "", published_h=1, event_at=datetime(2026, 10, 20, 8))
    new_dated = art(16, "Zebranie wiejskie w świetlicy", "", published_h=5, event_at=datetime(2026, 10, 21, 8))
    pool = [new, old_far, old_low, newer, too_old, other_day, new_dated]
    emb = {10: vec(1.0), 11: vec(0.885, 0.466), 12: vec(0.5, 0.866), 13: vec(0.9, 0.436),
           14: vec(0.99, 0.141), 15: vec(0.0, 0.0, 1.0), 16: vec(0.0, 0.0, 1.0)}
    keys = {a.id: story_key(a, emb[a.id]) for a in pool}
    got = [a.id for a in sj.gray_zone_candidates(new, pool, keys)]
    check("starszy wpis w szarej strefie → do sędziego (wyłączenia w różnych wsiach spoza gminy)", got == [11], got)
    check("nowszy wpis nie jest porównywany drugi raz (każda para raz)", 13 not in got)
    check("starszy niż okno 3 dni — pominięty", 14 not in got)
    check("podobieństwo 0,50 — poza szarą strefą", 12 not in got)
    got_dated = [a.id for a in sj.gray_zone_candidates(new_dated, pool, keys)]
    check("weto terminu PRZED sędzią (zebranie 20.10 vs 21.10)", 15 not in got_dated, got_dated)

    many = [art(100 + i, f"Wpis {i}", "", published_h=1) for i in range(8)]
    base = art(99, "Wpis bazowy", "", published_h=5)
    keys2 = {a.id: story_key(a, vec(0.9, 0.436)) for a in many}
    keys2[99] = story_key(base, vec(1.0))
    check(f"najwyżej {sj.MAX_CANDIDATES_PER_ARTICLE} kandydatów na wpis",
          len(sj.gray_zone_candidates(base, many + [base], keys2)) == sj.MAX_CANDIDATES_PER_ARTICLE)


async def section_db() -> None:
    """Na lokalnej bazie z atrapą sędziego. Commit podmieniony na flush, na końcu rollback."""
    from src.database.connection import async_session
    print("\n3️⃣  link_new_stories na lokalnej bazie (atrapa sędziego, zmiany wycofane)")
    async with async_session() as session:
        from sqlalchemy import select, func
        from src.database.schema import Article
        last = (await session.execute(select(func.max(Article.published_at)))).scalar()
        if last is None:
            check("brak artykułów lokalnie — pominięte", True)
            return
        session.commit = session.flush  # nic nie trafia do bazy
        calls = []

        async def always_same(a, b, session=None):
            calls.append((a.id, b.id))
            return sj.SAME

        try:
            stats = await sj.link_new_stories(session, now=last + timedelta(hours=1), judge=always_same,
                                              max_judgments=10)
            check("sędzia dostał pary z szarej strefy", stats["judged"] == len(calls) and stats["judged"] > 0, stats)
            linked = [b for _a, b in calls]
            rows = (await session.execute(select(Article).where(Article.story_id.isnot(None)))).scalars().all()
            pub = {r.id: r.published_at for r in rows}
            # korzeń = wpis opublikowany NAJWCZEŚNIEJ (id bywa wyższe — pobrany później)
            roots_ok = all(pub.get(r.story_id, r.published_at) <= r.published_at for r in rows)
            check("story_id wskazuje wpis opublikowany najwcześniej", roots_ok and len(rows) > 0, len(rows))
            check("oceniony wpis ma znacznik (nie wróci do sędziego)",
                  all(r.story_checked_at is not None for r in rows if r.id in linked))
            check("limit przebiegu przestrzegany", stats["judged"] <= 10, stats)
        finally:
            await session.rollback()

        session2_calls = []

        async def broken(a, b, session=None):
            session2_calls.append(1)
            return None

    async with async_session() as session:
        session.commit = session.flush
        try:
            stats = await sj.link_new_stories(session, now=last + timedelta(hours=1), judge=broken, max_judgments=3)
            check("błąd modelu: nic nie połączone", stats["linked"] == 0 and session2_calls, stats)
            unchecked_after = (await session.execute(
                select(func.count()).select_from(Article).where(Article.story_checked_at.isnot(None))
            )).scalar()
            check("…żaden wpis z nieudaną oceną nie dostał znacznika", unchecked_after == stats["checked"],
                  (unchecked_after, stats))
        finally:
            await session.rollback()


async def section_live() -> None:
    print("\n4️⃣  Prawdziwy sędzia na 38 ocenionych parach (model)")
    data = json.loads((Path(__file__).parent / "fixtures/story_judge_pairs.json").read_text())

    def obj(x):
        return SimpleNamespace(display_title=x["tytul"], title=x["tytul"], event_at=x["termin"],
                               summary=x["tresc"], content="")

    pairs = [p for p in data["pary"] if p["ocena"] != "niepewna"]
    verdicts = await asyncio.gather(*[sj.ask_model(obj(p["a"]), obj(p["b"])) for p in pairs])
    false_merges = [p["nr"] for p, v in zip(pairs, verdicts) if p["ocena"] == "inna" and v in (sj.SAME, sj.UPDATE)]
    same = [(p, v) for p, v in zip(pairs, verdicts) if p["ocena"] != "inna"]
    caught = sum(1 for _p, v in same if v in (sj.SAME, sj.UPDATE))
    errors = sum(1 for v in verdicts if v is None)
    check("ZERO sklejonych różnych spraw (warunek konieczny)", not false_merges, false_merges)
    check("zwinięte ≥ 85% duplikatów i odsłon", caught >= 0.85 * len(same), f"{caught}/{len(same)}")
    check("bez błędów modelu", errors == 0, errors)


if __name__ == "__main__":
    section_story_axis()
    section_candidates()
    if "--db" in sys.argv:
        asyncio.run(section_db())
    if "--live" in sys.argv:
        asyncio.run(section_live())
    passed = sum(results)
    print(f"\n{'✅' if passed == len(results) else '❌'} {passed}/{len(results)} sprawdzeń")
    sys.exit(0 if passed == len(results) else 1)
