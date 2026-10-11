"""
Przelewy24 + BLIK Payment Service
Dokumentacja API: https://developers.przelewy24.pl/
"""
import hashlib
import uuid
import logging
from enum import Enum
from typing import Optional

import httpx

from src.config import settings

logger = logging.getLogger("P24Service")

# P24 API URLs
P24_BASE_URL_SANDBOX = "https://sandbox.przelewy24.pl"
P24_BASE_URL_PROD = "https://secure.przelewy24.pl"

# Ceny subskrypcji w groszach (1 PLN = 100 groszy)
SUBSCRIPTION_PRICES = {
    "premium": {"monthly": 999, "yearly": 8400},    # 9.99 PLN | 84 PLN
    "business": {"monthly": 4900, "yearly": 49000}, # Firma lokalna: 49 PLN | 490 PLN (B2B)
}


class VerifyResult(str, Enum):
    """Wynik weryfikacji płatności w P24 (audyt 11.10.2026, F-023).

    Do 11.10 `verify_transaction` zwracało bool, więc timeout albo 5xx po stronie
    P24 wyglądały jak ODMOWA: webhook oznaczał zapłaconą subskrypcję jako
    wygasłą i odpowiadał 200 — P24 uznawał IPN za doręczony i nie ponawiał.
    Klient płacił i nie dostawał planu. Błąd transportu to „nie wiem”, nie „nie”.
    """
    VERIFIED = "verified"   # P24 potwierdziło płatność
    REJECTED = "rejected"   # P24 odpowiedziało, że transakcja nie przechodzi
    ERROR = "error"         # brak odpowiedzi / 5xx — stan nieznany, P24 ma ponowić IPN


class P24Service:
    """Klient do API Przelewy24"""

    def __init__(self):
        self.merchant_id = settings.P24_MERCHANT_ID
        self.pos_id = settings.P24_POS_ID or settings.P24_MERCHANT_ID
        self.crc_key = settings.P24_CRC_KEY
        self.api_key = settings.P24_API_KEY
        self.sandbox = settings.P24_SANDBOX
        self.base_url = P24_BASE_URL_SANDBOX if self.sandbox else P24_BASE_URL_PROD

    def is_configured(self) -> bool:
        """Czy komplet kluczy z panelu P24 jest w środowisku (bez nich nie da się zarejestrować transakcji)"""
        return bool(self.merchant_id and self.crc_key and self.api_key)

    def _auth(self) -> httpx.BasicAuth:
        """Basic Auth: pos_id jako login, api_key jako hasło"""
        return httpx.BasicAuth(str(self.pos_id), self.api_key)

    def _sign_transaction(self, session_id: str, amount: int, currency: str = "PLN") -> str:
        """Generuje podpis SHA384 dla transakcji P24"""
        sign_str = f'{{"sessionId":"{session_id}","merchantId":{self.merchant_id},"amount":{amount},"currency":"{currency}","crc":"{self.crc_key}"}}'
        return hashlib.sha384(sign_str.encode("utf-8")).hexdigest()

    def _sign_verify(self, session_id: str, order_id: str, amount: int, currency: str = "PLN") -> str:
        """Generuje podpis SHA384 do weryfikacji transakcji"""
        sign_str = f'{{"sessionId":"{session_id}","orderId":{order_id},"amount":{amount},"currency":"{currency}","crc":"{self.crc_key}"}}'
        return hashlib.sha384(sign_str.encode("utf-8")).hexdigest()

    def generate_session_id(self, user_id: int, tier: str, period: str) -> str:
        """Generuje unikalny session_id dla transakcji"""
        unique = uuid.uuid4().hex[:8]
        return f"COM-{user_id}-{tier}-{period}-{unique}"

    def get_price(self, tier: str, period: str) -> int:
        """Zwraca cenę w groszach"""
        prices = SUBSCRIPTION_PRICES.get(tier, {})
        return prices.get(period, 0)

    async def register_transaction(
        self,
        session_id: str,
        amount: int,
        email: str,
        description: str,
        return_url: str,
        notify_url: str,
        currency: str = "PLN",
        client_name: str = "",
    ) -> dict:
        """
        Rejestruje transakcję w P24 i zwraca token do przekierowania.

        Returns:
            {"token": "...", "redirect_url": "...", "order_id": "..."}
        """
        if not self.is_configured():
            raise RuntimeError("Przelewy24 nie jest skonfigurowane (brak P24_MERCHANT_ID/P24_CRC_KEY/P24_API_KEY w .env)")

        sign = self._sign_transaction(session_id, amount, currency)

        payload = {
            "merchantId": self.merchant_id,
            "posId": self.pos_id,
            "sessionId": session_id,
            "amount": amount,
            "currency": currency,
            "description": description,
            "email": email,
            "country": "PL",
            "language": "pl",
            "urlReturn": return_url,
            "urlStatus": notify_url,
            "sign": sign,
            "encoding": "UTF-8",
        }
        # Imię i nazwisko idzie jednym polem "client" (max 50 znaków) — API v1 nie zna
        # firstName/lastName i odrzuca cały request z "Invalid request!"
        if client_name:
            payload["client"] = client_name[:50]

        # Asynchronicznie: synchroniczne `requests` w trasie async blokowało CAŁY
        # backend (jeden worker) na czas odpowiedzi P24 — do 15 s (F-023)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v1/transaction/register",
                    json=payload,
                    auth=self._auth(),
                )
            if not resp.is_success:
                # Przy 4xx P24 opisuje przyczynę w treści odpowiedzi — bez niej zostaje
                # samo "400 Bad Request" i nie wiadomo, które pole jest wadliwe
                logger.error(f"P24 register HTTP {resp.status_code}: {resp.text[:500]}")
                raise RuntimeError(f"Przelewy24 odrzuciło zamówienie (HTTP {resp.status_code}): {resp.text[:200]}")

            data = resp.json()

            if data.get("error"):
                logger.error(f"P24 register error: {data}")
                raise RuntimeError(f"P24 error: {data.get('errorMessage', 'Unknown error')}")

            token = data["data"]["token"]
            redirect_url = f"{self.base_url}/trnRequest/{token}"

            return {
                "token": token,
                "redirect_url": redirect_url,
                "session_id": session_id,
            }
        except httpx.HTTPError as e:
            logger.error(f"P24 register request failed: {e}")
            raise RuntimeError(f"Błąd połączenia z Przelewy24: {e}")

    async def verify_transaction(
        self, session_id: str, order_id: str, amount: int, currency: str = "PLN"
    ) -> VerifyResult:
        """Weryfikuje transakcję po otrzymaniu IPN od P24. Trzy stany — patrz `VerifyResult`."""
        if not self.is_configured():
            logger.error("P24 verify: brak kluczy — stan nieznany")
            return VerifyResult.ERROR

        sign = self._sign_verify(session_id, order_id, amount, currency)

        payload = {
            "merchantId": self.merchant_id,
            "posId": self.pos_id,
            "sessionId": session_id,
            "amount": amount,
            "currency": currency,
            "orderId": int(order_id),
            "sign": sign,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.put(
                    f"{self.base_url}/api/v1/transaction/verify",
                    json=payload,
                    auth=self._auth(),
                )
        except httpx.HTTPError as e:
            logger.error(f"P24 verify: brak odpowiedzi ({type(e).__name__}: {e})")
            return VerifyResult.ERROR

        # 5xx i 429 = P24 nie rozstrzygnęło; 4xx = rozstrzygnęło, że nie
        if resp.status_code >= 500 or resp.status_code == 429:
            logger.error(f"P24 verify HTTP {resp.status_code}: {resp.text[:300]}")
            return VerifyResult.ERROR
        if resp.status_code >= 400:
            logger.error(f"P24 verify odrzucone HTTP {resp.status_code}: {resp.text[:300]}")
            return VerifyResult.REJECTED

        try:
            data = resp.json()
        except ValueError:
            logger.error(f"P24 verify: odpowiedź nie jest JSON-em: {resp.text[:300]}")
            return VerifyResult.ERROR

        if data.get("error"):
            logger.error(f"P24 verify error: {data}")
            return VerifyResult.REJECTED
        if data.get("data", {}).get("status", "") == "success":
            return VerifyResult.VERIFIED
        logger.error(f"P24 verify: nieoczekiwana odpowiedź {data}")
        return VerifyResult.REJECTED

    async def get_transaction_status(self, session_id: str) -> Optional[dict]:
        """Sprawdza status transakcji po session_id"""
        if not self.is_configured():
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/transaction/by/sessionId/{session_id}",
                    auth=self._auth(),
                )
            resp.raise_for_status()
            return resp.json().get("data")
        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"P24 status request failed: {e}")
            return None


# Singleton
p24_service = P24Service()
