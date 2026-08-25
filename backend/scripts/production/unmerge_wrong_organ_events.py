"""
Rozscalenie posiedzeń zlepionych w jedno wydarzenie (2026-08-25)

**Skąd to.** Dedup wydarzeń rozstrzygał tożsamość samym podobieństwem
embeddingów w obrębie doby, a dzień sesji Rady to zawsze komplet posiedzeń:
komisje rano, sesja przed południem, ta sama sala, ten sam porządek obrad
w opisie. 24.08 kalendarz stracił przez to XXIV sesję Rady Gminy — wjechała
jako powtórka Komisji Budżetu i zniknęła z kalendarza, briefingu, newslettera
oraz narzędzia `upcoming_events` na dwa dni przed terminem.

Pomiar z 25.08 (8 par z produkcji) pokazał, że progu tu nie ma: „XXIV sesja"
kontra „Komisja Budżetu" = 0,909, a dwa opisy tej samej mszy = 0,790. Dlatego
`same_event` dostało weto organu — i dlatego ten skrypt przechodzi po tym, co
zdążyło się scalić WCZEŚNIEJ.

**Nie liczy embeddingów.** Weto organu czyta tytuły, więc przegląd jest czysto
tekstowy i nie kosztuje ani grosza — inaczej niż `dedupe_events`, który dla
520 scalonych wpisów musiałby policzyć wektory na nowo (powtórek nie embedujemy).

⚠️ Rozscalony wpis dostaje `embedded = False`: jego embedding nigdy nie trafił
do bazy (ekstraktor zapisuje tylko wzorce), a bez chunku wydarzenie jest
niewidzialne dla przyszłego dedupu i dla RAG. Job osadzeń dobierze je przy
najbliższym przebiegu — `_embed_events` nie ma okna czasowego.

Bez `--apply` tylko pokazuje, co by zmienił.

Użycie:
    cd backend && python -u -m scripts.production.unmerge_wrong_organ_events [--apply]
"""
import argparse
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.ai.event_extractor import _organ_key
from src.config import settings
from src.database.schema import Event


async def main(apply: bool) -> int:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        merged = (await session.execute(
            select(Event).where(Event.canonical_id.is_not(None))
            .order_by(Event.event_date.desc())
        )).scalars().all()

        if not merged:
            print("Brak scalonych wydarzeń — nie ma czego przeglądać.")
            return 0

        canonical_ids = {e.canonical_id for e in merged}
        canonicals = {
            e.id: e for e in (await session.execute(
                select(Event).where(Event.id.in_(canonical_ids))
            )).scalars().all()
        }

        do_rozscalenia = []
        for dup in merged:
            head = canonicals.get(dup.canonical_id)
            if not head:
                continue
            klucz, klucz_head = _organ_key(dup.title), _organ_key(head.title)
            if klucz and klucz_head and klucz != klucz_head:
                do_rozscalenia.append((dup, head, klucz, klucz_head))

        print(f"Scalonych wydarzeń w bazie: {len(merged)}")
        print(f"Do rozscalenia (różny organ): {len(do_rozscalenia)}")
        print()

        for dup, head, klucz, klucz_head in do_rozscalenia:
            kiedy = dup.event_date.strftime("%d.%m.%Y %H:%M") if dup.event_date else "—"
            print(f"  #{dup.id} {kiedy}  „{(dup.title or '')[:58]}”")
            print(f"      wraca z    #{head.id} „{(head.title or '')[:58]}”")
            print(f"      organ: {klucz}  ≠  {klucz_head}")

        if not do_rozscalenia:
            return 0

        if not apply:
            print()
            print("To był podgląd. Uruchom z --apply, żeby zapisać.")
            return 0

        for dup, _, _, _ in do_rozscalenia:
            dup.canonical_id = None
            # Powtórki nie embedujemy, więc rozscalony wpis nie ma chunku —
            # bez tego nie zobaczy go ani RAG, ani dedup kolejnych wydarzeń.
            dup.embedded = False
            session.add(dup)
        await session.commit()

        print()
        print(f"✓ Rozscalono {len(do_rozscalenia)} wydarzeń; "
              f"embeddingi dobierze najbliższy przebieg embedding_job.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="zapisz zmiany")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.apply)))
