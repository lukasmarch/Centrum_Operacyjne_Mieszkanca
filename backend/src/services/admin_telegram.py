"""
Krótka wiadomość na Telegram admina.

`council_job._notify_telegram` zostaje osobno: niesie przycisk do strony
akceptacji i własny układ. Tu idzie zwykły tekst, a błąd wysyłki nigdy
nie wychodzi poza funkcję — alert nie może położyć joba, który go wysyła.

`buttons` — przyciski-LINKI (`url`), nigdy `callback_data`: bot jest wspólny
z n8n, który odbiera kliknięcia przycisków W2 webhookiem. Własny webhook
zabrałby mu te zdarzenia. Link prowadzi na stronę, gdzie decyzja idzie POST-em.
"""
from typing import List, Optional, Tuple

from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("AdminTelegram")


def _is_public_url(url: str) -> bool:
    """Telegram odrzuca CAŁĄ wiadomość (400), gdy przycisk prowadzi na localhost."""
    return not any(m in url for m in ("localhost", "127.0.0.1", "0.0.0.0", "://192.168."))


def send_admin_telegram(text: str, buttons: Optional[List[Tuple[str, str]]] = None) -> bool:
    """Zwraca True, gdy Telegram przyjął wiadomość. `buttons` = [(etykieta, adres)]."""
    token, chat = settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID
    if not token or not chat:
        logger.warning("Brak TELEGRAM_BOT_TOKEN/CHAT_ID — alert tylko w logu: %s", text)
        return False
    try:
        import httpx

        # Bez parse_mode: treść bywa z wyjątku i potrafi mieć niedomknięte * albo _.
        payload = {"chat_id": chat, "text": text, "disable_web_page_preview": True}
        if buttons:
            if all(_is_public_url(url) for _label, url in buttons):
                payload["reply_markup"] = {"inline_keyboard": [[
                    {"text": label, "url": url} for label, url in buttons
                ]]}
            else:
                # Dewelopersko: adresy w treści zamiast przycisków, żeby wiadomość doszła
                payload["text"] += "\n\n" + "\n".join(f"{label}: {url}" for label, url in buttons)
        payload["text"] = payload["text"][:3900]
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=20.0,
        )
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        # httpx wkleja adres z tokenem do treści wyjątku (patrz council_job._scrub_token).
        logger.error("Telegram nie przyjął alertu: %s", str(exc).replace(token, "***"))
        return False
