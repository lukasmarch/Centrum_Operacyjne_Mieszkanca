"""
Wspólny zapis kosztów wywołań AI do api_cost_log (kontrola marży planów).

Czat loguje się w chat.py (estymata 60/40); ten moduł obsługuje resztę
pipeline'u: kategoryzację artykułów, daily summary i embeddingi.
"""
from typing import Optional

from src.database.vectors import APICostLog
from src.utils.logger import setup_logger

logger = setup_logger("CostTracker")

# USD za 1M tokenów (cennik OpenAI, 07.2026)
MODEL_PRICES = {
    "gpt-4o":                 {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":            {"input": 0.15, "output": 0.60},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}


def log_api_cost(
    session,
    model: str,
    tokens_input: int,
    tokens_output: int,
    endpoint: str,
    user_id: Optional[int] = None,
    service: str = "openai",
) -> None:
    """Dodaje wpis APICostLog do sesji (bez commita — commituje wołający).

    Nigdy nie rzuca — błąd logowania kosztu nie może psuć pipeline'u.
    """
    try:
        if not tokens_input and not tokens_output:
            return
        prices = MODEL_PRICES.get(model, {"input": 0.0, "output": 0.0})
        cost = (
            tokens_input * prices["input"] / 1_000_000
            + tokens_output * prices["output"] / 1_000_000
        )
        session.add(APICostLog(
            service=service,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            estimated_cost_usd=round(cost, 8),
            endpoint=endpoint,
            user_id=user_id,
        ))
    except Exception as e:
        logger.warning(f"Nie udało się zalogować kosztu API ({endpoint}): {e}")
