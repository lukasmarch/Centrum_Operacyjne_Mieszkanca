"""
Przelewy24 + BLIK Payment Service
Dokumentacja API: https://developers.przelewy24.pl/
"""
import hashlib
import uuid
import logging
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

from src.config import settings

logger = logging.getLogger("P24Service")

# P24 API URLs
P24_BASE_URL_SANDBOX = "https://sandbox.przelewy24.pl"
P24_BASE_URL_PROD = "https://secure.przelewy24.pl"

# Ceny subskrypcji w groszach (1 PLN = 100 groszy)
SUBSCRIPTION_PRICES = {
    "premium": {"monthly": 999, "yearly": 8400},   # 9.99 PLN | 84 PLN
    "business": {"monthly": 1999, "yearly": 16900}, # 19.99 PLN | 169 PLN
}


class P24Service:
    """Klient do API Przelewy24"""

    def __init__(self):
        self.merchant_id = settings.P24_MERCHANT_ID
        self.pos_id = settings.P24_POS_ID or settings.P24_MERCHANT_ID
        self.crc_key = settings.P24_CRC_KEY
        self.api_key = settings.P24_API_KEY
        self.sandbox = settings.P24_SANDBOX
        self.base_url = P24_BASE_URL_SANDBOX if self.sandbox else P24_BASE_URL_PROD

    def _is_configured(self) -> bool:
        return bool(self.merchant_id and self.crc_key and self.api_key)

    def _auth(self) -> HTTPBasicAuth:
        """Basic Auth: pos_id jako login, api_key jako hasło"""
        return HTTPBasicAuth(str(self.pos_id), self.api_key)

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

    def register_transaction(
        self,
        session_id: str,
        amount: int,
        email: str,
        description: str,
        return_url: str,
        notify_url: str,
        currency: str = "PLN",
        first_name: str = "",
        last_name: str = "",
    ) -> dict:
        """
        Rejestruje transakcję w P24 i zwraca token do przekierowania.

        Returns:
            {"token": "...", "redirect_url": "...", "order_id": "..."}
        """
        if not self._is_configured():
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
        if first_name:
            payload["firstName"] = first_name
        if last_name:
            payload["lastName"] = last_name

        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/transaction/register",
                json=payload,
                auth=self._auth(),
                timeout=15,
            )
            resp.raise_for_status()
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
        except requests.RequestException as e:
            logger.error(f"P24 register request failed: {e}")
            raise RuntimeError(f"Błąd połączenia z Przelewy24: {e}")

    def verify_transaction(self, session_id: str, order_id: str, amount: int, currency: str = "PLN") -> bool:
        """
        Weryfikuje transakcję po otrzymaniu IPN od P24.

        Returns:
            True jeśli transakcja zweryfikowana poprawnie
        """
        if not self._is_configured():
            raise RuntimeError("Przelewy24 nie jest skonfigurowane")

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
            resp = requests.put(
                f"{self.base_url}/api/v1/transaction/verify",
                json=payload,
                auth=self._auth(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("error"):
                logger.error(f"P24 verify error: {data}")
                return False

            status = data.get("data", {}).get("status", "")
            return status == "success"
        except requests.RequestException as e:
            logger.error(f"P24 verify request failed: {e}")
            return False

    def get_transaction_status(self, session_id: str) -> Optional[dict]:
        """Sprawdza status transakcji po session_id"""
        if not self._is_configured():
            return None
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/transaction/{session_id}",
                auth=self._auth(),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data")
        except requests.RequestException as e:
            logger.error(f"P24 status request failed: {e}")
            return None


# Singleton
p24_service = P24Service()
