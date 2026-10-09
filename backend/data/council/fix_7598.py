"""Podmienia skrót sesji XXV (external_id 7598) na wersję poprawioną ręcznie z transkryptu.

Wiersz `pending` albo `rejected` (30.09 stara wersja została odrzucona z Telegrama,
zanim poprawka weszła) wraca do `pending` z NOWYM tokenem — opublikowanego nie ruszamy. Publikuje dalej człowiek
na stronie akceptacji. Uruchamiane w kontenerze backendu.
"""
import asyncio
import json
import secrets

from sqlmodel import select

from src.config import settings
from src.database.connection import async_session
from src.database.schema import CouncilSession


async def main() -> None:
    fixed = open("/tmp/sesja_7598.summary_poprawiony.json", encoding="utf-8").read()
    points = json.loads(fixed)["points"]
    async with async_session() as s:
        row = (await s.execute(
            select(CouncilSession).where(CouncilSession.external_id == "7598")
        )).scalars().first()
        if row is None or row.status not in ("pending", "rejected"):
            print("PRZERWANE: brak wiersza albo status inny niż pending:", row and row.status)
            return
        row.summary_json = json.dumps(json.loads(fixed), ensure_ascii=False)
        # Zdania sprawdzone człowiekiem z transkryptem — stare zakreślenia dotyczyły
        # wersji, której już nie ma.
        row.claims_total = len(points)
        row.claims_flagged = 0
        row.claims_flagged_text = None
        row.status = "pending"
        row.reviewed_at = None
        row.reviewed_by = None
        row.review_token = secrets.token_urlsafe(32)
        s.add(row)
        await s.commit()
        print("ZAPISANO:", json.loads(row.summary_json)["headline"])
        print("NOWY LINK DO AKCEPTACJI:", f"{settings.API_URL}/api/council/review/{row.review_token}")


asyncio.run(main())
