"""
Krótka wiadomość na Telegram admina — dla alertów bez przycisków.

`council_job._notify_telegram` zostaje osobno: niesie przycisk do strony
akceptacji i własny układ. Tu idzie zwykły tekst, a błąd wysyłki nigdy
nie wychodzi poza funkcję — alert nie może położyć joba, który go wysyła.
"""
from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("AdminTelegram")


def send_admin_telegram(text: str) -> bool:
    """Zwraca True, gdy Telegram przyjął wiadomość."""
    token, chat = settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID
    if not token or not chat:
        logger.warning("Brak TELEGRAM_BOT_TOKEN/CHAT_ID — alert tylko w logu: %s", text)
        return False
    try:
        import httpx

        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            # Bez parse_mode: treść bywa z wyjątku i potrafi mieć niedomknięte * albo _.
            json={"chat_id": chat, "text": text[:3900], "disable_web_page_preview": True},
            timeout=20.0,
        )
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        # httpx wkleja adres z tokenem do treści wyjątku (patrz council_job._scrub_token).
        logger.error("Telegram nie przyjął alertu: %s", str(exc).replace(token, "***"))
        return False
