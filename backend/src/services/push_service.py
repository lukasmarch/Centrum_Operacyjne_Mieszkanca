"""
Push Notifications Service (Sprint 5C)

Wysyłanie Web Push Notifications via pywebpush.
Obsługuje cztery typy triggerów:
- Alerty bezpieczeństwa (emergency/fire reports) → wszyscy subskrybenci
- Smog alert (PM2.5 > 50) → kategoria "powietrze"
- Dzienne podsumowanie → kategoria "artykuly"
- Nowe pilne artykuły → kategoria "artykuly"
"""
import json
import asyncio
from datetime import datetime
from typing import Optional, List

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("PushService")


def _send_push_notification_sync(endpoint: str, p256dh: str, auth: str,
                                   title: str, body: str,
                                   url: str = "/", icon: str = "/icon-192.png") -> bool:
    """
    Synchronous push notification send via pywebpush.
    Called via asyncio.to_thread() from async context.
    """
    try:
        from pywebpush import webpush, WebPushException

        subscription_info = {
            "endpoint": endpoint,
            "keys": {
                "p256dh": p256dh,
                "auth": auth,
            }
        }

        data = json.dumps({
            "title": title,
            "body": body,
            "url": url,
            "icon": icon,
        })

        vapid_claims = {"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"}

        # pywebpush accepts the private key as base64url DER string
        webpush(
            subscription_info=subscription_info,
            data=data,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims=vapid_claims,
            content_encoding="aes128gcm",
        )
        return True

    except Exception as e:
        error_str = str(e)
        # 410 Gone = subscription expired, should be deactivated
        if "410" in error_str or "404" in error_str:
            logger.warning(f"Subscription expired/not found: {endpoint[:50]}...")
            return False
        logger.error(f"Push send error: {e}")
        return False


class PushService:
    """
    Serwis push notifications.
    Metody async – można wywołać z endpointów FastAPI i schedulerów.
    """

    def _is_configured(self) -> bool:
        return bool(settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY)

    async def send_push(
        self,
        endpoint: str,
        p256dh: str,
        auth: str,
        title: str,
        body: str,
        url: str = "/",
        icon: str = "/icon-192.png",
    ) -> bool:
        """Wyślij pojedyncze push notification."""
        if not self._is_configured():
            logger.warning("VAPID keys not configured – skipping push")
            return False

        try:
            success = await asyncio.to_thread(
                _send_push_notification_sync,
                endpoint, p256dh, auth, title, body, url, icon
            )
            return success
        except Exception as e:
            logger.error(f"Push notification error: {e}")
            return False

    async def send_to_category(
        self,
        session: AsyncSession,
        category: str,
        title: str,
        body: str,
        url: str = "/",
        icon: str = "/icon-192.png",
    ) -> int:
        """
        Wyślij push do wszystkich aktywnych subskrybentów danej kategorii.
        Zwraca liczbę wysłanych powiadomień.
        """
        if not self._is_configured():
            logger.warning("VAPID keys not configured – skipping push broadcast")
            return 0

        from src.database.schema import PushSubscription

        # Pobierz aktywne subskrypcje z daną kategorią
        result = await session.execute(
            select(PushSubscription).where(PushSubscription.active == True)
        )
        subscriptions = result.scalars().all()

        # Filtruj po kategorii (lub wyślij wszystkim jeśli kategoria "alerty")
        if category != "alerty":
            subscriptions = [
                s for s in subscriptions
                if not s.categories or category in s.categories
            ]

        if not subscriptions:
            logger.info(f"No active push subscriptions for category '{category}'")
            return 0

        logger.info(f"Sending push to {len(subscriptions)} subscribers (category: {category})")

        sent_count = 0
        expired_ids = []

        for sub in subscriptions:
            success = await self.send_push(
                endpoint=sub.endpoint,
                p256dh=sub.p256dh,
                auth=sub.auth,
                title=title,
                body=body,
                url=url,
                icon=icon,
            )
            if success:
                sent_count += 1
                sub.last_used_at = datetime.utcnow()
                session.add(sub)
            else:
                # Mark expired subscriptions for deactivation
                expired_ids.append(sub.id)

        # Deactivate expired subscriptions
        if expired_ids:
            result = await session.execute(
                select(PushSubscription).where(
                    PushSubscription.id.in_(expired_ids)
                )
            )
            expired_subs = result.scalars().all()
            for sub in expired_subs:
                sub.active = False
                session.add(sub)
            logger.info(f"Deactivated {len(expired_ids)} expired push subscriptions")

        await session.commit()
        logger.info(f"Push notifications sent: {sent_count}/{len(subscriptions)}")
        return sent_count

    async def send_emergency_alert(self, session: AsyncSession, report) -> int:
        """
        Natychmiastowy alert dla zgłoszeń emergency/fire.
        Wysyłany do WSZYSTKICH aktywnych subskrybentów niezależnie od kategorii.
        """
        category_labels = {
            "emergency": "ALERT BEZPIECZENSTWA",
            "fire": "ALERT POZAROWY",
        }
        label = category_labels.get(report.category, "ALERT")

        title = f"CENTRUM OPERACYJNE: {label}"
        body = f"{report.title}"
        if report.location_name:
            body += f" – {report.location_name}"

        url = f"/zgloszenia/{report.id}" if report.id else "/zgloszenia"

        # Send to all (pass "alerty" category = no filtering)
        return await self.send_to_category(
            session=session,
            category="alerty",
            title=title,
            body=body,
            url=url,
            icon="/icon-alert-192.png",
        )

    async def send_daily_summary_push(
        self, session: AsyncSession, headline: str
    ) -> int:
        """Powiadomienie po wygenerowaniu dziennego podsumowania."""
        return await self.send_to_category(
            session=session,
            category="artykuly",
            title="Dzienne podsumowanie gotowe",
            body=headline[:120] if headline else "Sprawdź co się dzieje w Gminie Rybno",
            url="/",
            icon="/icon-192.png",
        )

    async def send_air_alert_push(
        self, session: AsyncSession, pm25_value: float
    ) -> int:
        """Alert smogowy gdy PM2.5 > 50 µg/m³."""
        level = "bardzo wysokie" if pm25_value > 100 else "wysokie"
        return await self.send_to_category(
            session=session,
            category="powietrze",
            title=f"Alert smogowy – Rybno",
            body=f"Stężenie PM2.5: {pm25_value:.0f} µg/m³ ({level}). Ogranicz wychodzenie na zewnątrz.",
            url="/pogoda",
            icon="/icon-smog-192.png",
        )

    async def send_proactive_reminder(
        self,
        session: AsyncSession,
        user_ids: List[int],
        title: str,
        body: str,
        url: str = "/",
        icon: str = "/icon-192.png",
    ) -> int:
        """
        Proaktywne powiadomienie dla konkretnych Premium userów (po user_id).
        Używane przez proactive_alerts_job — śmietnik, mróz, awarie, BIP.
        Wysyła tylko do subskrypcji powiązanych z podanymi user_ids.
        """
        if not self._is_configured():
            logger.warning("VAPID keys not configured – skipping proactive push")
            return 0

        if not user_ids:
            return 0

        from src.database.schema import PushSubscription

        result = await session.execute(
            select(PushSubscription).where(
                PushSubscription.active == True,
                PushSubscription.user_id.in_(user_ids),
            )
        )
        subscriptions = result.scalars().all()

        if not subscriptions:
            logger.info(f"No push subscriptions for {len(user_ids)} premium users")
            return 0

        logger.info(f"Sending proactive push to {len(subscriptions)} subscriptions ({len(user_ids)} users)")

        sent_count = 0
        expired_ids = []

        for sub in subscriptions:
            success = await self.send_push(
                endpoint=sub.endpoint,
                p256dh=sub.p256dh,
                auth=sub.auth,
                title=title,
                body=body,
                url=url,
                icon=icon,
            )
            if success:
                sent_count += 1
                sub.last_used_at = datetime.utcnow()
                session.add(sub)
            else:
                expired_ids.append(sub.id)

        if expired_ids:
            exp_result = await session.execute(
                select(PushSubscription).where(PushSubscription.id.in_(expired_ids))
            )
            for sub in exp_result.scalars().all():
                sub.active = False
                session.add(sub)

        await session.commit()
        logger.info(f"Proactive push sent: {sent_count}/{len(subscriptions)}")
        return sent_count


# Singleton
push_service = PushService()
