"""
Strażnik kredytów OpenAI — co godzinę, alert na Telegram (2026-09-30).

**Dlaczego sonda, a nie nasłuch błędów.** Kredyty skończyły się dwa razy w miesiącu
(2.09 i 30.09) i za każdym razem nikt nie dostał sygnału: 30.09 w logu produkcji
nie było ANI JEDNEGO śladu `credit_balance_exhausted`, bo między wyczerpaniem
a doładowaniem żaden job akurat nie wołał modelu. Brak kredytów wychodził dopiero
przy następnej pracy — w najgorszym razie o 5:00, na briefingu i newsletterze.
Sonda pyta sama: jedno wywołanie gpt-4o-mini z `max_tokens=1` (ułamek centa
miesięcznie) wykrywa stan najpóźniej w godzinę, zanim zależy od niego mieszkaniec.

Alert tylko przy ZMIANIE stanu (działa → nie działa i z powrotem), nie co godzinę.
Stan w pamięci procesu: restart kontenera w trakcie awarii da jeden alert więcej,
co jest tańsze niż tabela na jedną flagę.
"""
from typing import Optional

from src.config import settings
from src.services.admin_telegram import send_admin_telegram
from src.utils.logger import setup_logger

logger = setup_logger("OpenAICreditJob")

# Kody OpenAI oznaczające „nie ma za co liczyć" — w odróżnieniu od chwilowego 429
# (limit tempa) i awarii sieci, które mijają same i nie są sprawą dla admina.
_NO_CREDIT_CODES = ("insufficient_quota", "credit_balance_exhausted", "billing_hard_limit_reached")

# None = jeszcze nie sprawdzano; True/False = stan z ostatniej sondy.
_last_ok: Optional[bool] = None


def _is_no_credit(exc: Exception) -> bool:
    text = str(exc)
    return any(code in text for code in _NO_CREDIT_CODES)


def probe_openai() -> Optional[str]:
    """None, gdy model odpowiada; inaczej opis przyczyny braku kredytów/klucza."""
    from openai import AuthenticationError, OpenAI

    try:
        OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30).chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ok"}],
            max_tokens=1,
        )
        return None
    except AuthenticationError:
        return "klucz OPENAI_API_KEY odrzucony (401)"
    except Exception as exc:  # noqa: BLE001
        if _is_no_credit(exc):
            return "brak kredytów na koncie OpenAI"
        # Chwilowe kłopoty (sieć, 5xx, limit tempa) — nie budzimy admina.
        logger.warning("Sonda OpenAI: chwilowy błąd, bez alertu: %s", str(exc)[:200])
        raise


def run_openai_credit_job() -> None:
    global _last_ok
    try:
        problem = probe_openai()
    except Exception:  # noqa: BLE001 — chwilowy błąd: stan bez zmian
        return

    if problem:
        logger.error("OpenAI nie działa: %s", problem)
        if _last_ok is not False:
            send_admin_telegram(
                f"🔴 OpenAI: {problem}.\n\n"
                "Stoi wszystko, co używa AI: kategoryzacja wiadomości, asystent, "
                "wyszukiwarka, briefing 5:00/7:00, newsletter 7:15, skróty sesji.\n\n"
                "Doładuj: https://platform.openai.com/settings/organization/billing/"
            )
        _last_ok = False
        return

    if _last_ok is False:
        send_admin_telegram("🟢 OpenAI znów odpowiada — AI na stronie działa.")
        logger.info("OpenAI znów odpowiada")
    _last_ok = True
