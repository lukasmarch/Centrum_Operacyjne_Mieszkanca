"""
Usunięcie kont testowych i porzuconych płatności (2026-08-21).

Baza produkcyjna zebrała konta z okresu budowy: dwa własne adresy testowe i jedno
już zanonimizowane (RODO). Zostają wyłącznie konto właściciela, pierwszy prawdziwy
użytkownik i JEDNO konto testowe.

Kasujemy ręcznie, a nie kaskadą z bazy: `conversations` i `subscriptions` mają
`ON DELETE NO ACTION`, więc `DELETE FROM users` bez tego skryptu kończy się
naruszeniem klucza obcego. Kolejność jest istotna — najpierw dzieci.

⚠️ `business_profiles` ma CASCADE. Usuwając konto z przypisanym profilem firmy,
kasujemy też ten profil. Skrypt wypisuje takie przypadki OSOBNO, przed pytaniem
o zgodę: profil `rejected` to na produkcji jedyna pamięć o odmowie przejęcia
wizytówki (`business_claim_log` żyje na gałęzi `strona-glowna-etap0`).

Domyślnie tylko pokazuje, co by zrobił. Kasuje dopiero z `--apply`.

Użycie:
    cd backend && python -m scripts.cleanup_test_accounts --emails a@x.pl,b@y.pl
    cd backend && python -m scripts.cleanup_test_accounts --emails a@x.pl --apply
"""
import argparse
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings

# Kolejność ma znaczenie: dzieci przed rodzicem. `conversations` musi pójść po
# `chat_messages`, bo wiadomości wiszą na rozmowie, nie na użytkowniku.
CHILD_DELETES = [
    ("chat_messages", "DELETE FROM chat_messages WHERE conversation_id IN "
                      "(SELECT id FROM conversations WHERE user_id = ANY(:ids))"),
    ("conversations", "DELETE FROM conversations WHERE user_id = ANY(:ids)"),
    ("subscriptions", "DELETE FROM subscriptions WHERE user_id = ANY(:ids)"),
    ("newsletter_subscribers", "DELETE FROM newsletter_subscribers WHERE user_id = ANY(:ids)"),
    ("push_subscriptions", "DELETE FROM push_subscriptions WHERE user_id = ANY(:ids)"),
    ("referrals", "DELETE FROM referrals WHERE referrer_id = ANY(:ids) OR referred_id = ANY(:ids)"),
    ("reports", "DELETE FROM reports WHERE user_id = ANY(:ids)"),
    ("business_profiles", "DELETE FROM business_profiles WHERE user_id = ANY(:ids)"),
]


async def main() -> int:
    parser = argparse.ArgumentParser(description="Usuwa wskazane konta wraz z danymi zależnymi")
    parser.add_argument("--emails", required=True, help="Adresy do usunięcia, po przecinku")
    parser.add_argument("--apply", action="store_true", help="Wykonaj usunięcie (domyślnie: podgląd)")
    args = parser.parse_args()

    emails = [e.strip() for e in args.emails.split(",") if e.strip()]
    if not emails:
        print("❌ Podaj co najmniej jeden adres")
        return 1

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        rows = (await conn.execute(
            text("SELECT id, email, tier, created_at FROM users WHERE email = ANY(:emails) ORDER BY id"),
            {"emails": emails},
        )).all()

        if not rows:
            print("❌ Żaden z podanych adresów nie istnieje w bazie")
            await engine.dispose()
            return 1

        ids = [r[0] for r in rows]
        print("=" * 62)
        print("KONTA DO USUNIĘCIA")
        print("=" * 62)
        for r in rows:
            print(f"  id={r[0]:<4} {r[1]:<40} {r[2]:<9} {r[3]:%Y-%m-%d}")

        missing = set(emails) - {r[1] for r in rows}
        if missing:
            print(f"\n  ⚠️  nie znaleziono: {', '.join(sorted(missing))}")

        # Wizytówki firm giną razem z kontem (CASCADE) — pokaż to, zanim cokolwiek zniknie
        profiles = (await conn.execute(
            text("SELECT id, business_id, claim_status FROM business_profiles WHERE user_id = ANY(:ids)"),
            {"ids": ids},
        )).all()
        if profiles:
            print("\n  ⚠️  Zniknie też wizytówka firmy (CASCADE):")
            for p in profiles:
                print(f"       profil {p[0]} → firma {p[1]}, status przejęcia: {p[2]}")

        print("\nDane zależne:")
        planned = []
        for label, stmt in CHILD_DELETES:
            count_sql = stmt.replace("DELETE FROM", "SELECT COUNT(*) FROM", 1)
            n = (await conn.execute(text(count_sql), {"ids": ids})).scalar()
            if n:
                print(f"  {label:<24} {n}")
            planned.append((label, stmt))

        if not args.apply:
            print("\n👀 Podgląd — nic nie zostało usunięte. Powtórz z --apply.")
            await engine.dispose()
            return 0

        for label, stmt in planned:
            result = await conn.execute(text(stmt), {"ids": ids})
            if result.rowcount:
                print(f"  🗑️  {label}: {result.rowcount}")

        result = await conn.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": ids})
        print(f"  🗑️  users: {result.rowcount}")

    await engine.dispose()
    print("\n✅ Gotowe")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
