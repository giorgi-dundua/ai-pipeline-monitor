import logging
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Optional
import httpx

logger = logging.getLogger(__name__)

# 1. SHARED CONSTANTS
PRICING_URL = "https://raw.githubusercontent.com/pydantic/genai-prices/refs/heads/main/prices/data_slim.json"
PROVIDER_ID = "anthropic"
M_TOK = Decimal("1000000")

# Role-Based Model Identifiers
MODEL_PREMIUM = "claude-opus-4-6"
MODEL_BALANCED = "claude-sonnet-4-6"
MODEL_FAST     = "claude-haiku-4-5"

# 2. THE SAFETY NET (Fallback Pricing)
FALLBACK_PRICING: Dict[str, Dict[str, Decimal]] = {
    MODEL_PREMIUM: {
        "input":  Decimal("5.0") / M_TOK,
        "output": Decimal("25.0") / M_TOK, 
    },
    MODEL_BALANCED: {
        "input":  Decimal("3.0") / M_TOK,
        "output": Decimal("15.0") / M_TOK,
    },
    MODEL_FAST: {
        "input":  Decimal("1.0") / M_TOK,
        "output": Decimal("5.0") / M_TOK,
    }
}

# 3. GLOBAL STATE
CURRENT_PRICING = FALLBACK_PRICING.copy()
PRICING_VERSION: datetime = datetime.now(timezone.utc)

@dataclass(frozen=True)
class RequestMetrics:
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: Decimal
    success: bool
    pricing_version: datetime
    error_type: Optional[str] = None

def update_pricing_registry():
    """Fetches live prices and updates the in-memory registry."""
    global CURRENT_PRICING, PRICING_VERSION
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(PRICING_URL)
            response.raise_for_status()
            data = response.json()
            
        # Step into the 'anthropic' provider block
        anthropic_data = next((p for p in data if p["id"] == PROVIDER_ID), None)
        if not anthropic_data:
            return

        new_prices = {}
        for model in anthropic_data.get("models", []):
            model_id = model.get("id")
            
            if model_id in FALLBACK_PRICING:
                price_data = model.get("prices")
                
                # Handle cases where prices might be a list of date-constrained rules
                if isinstance(price_data, list):
                    price_data = price_data[-1].get("prices", {})

                input_m = Decimal(str(price_data.get("input_mtok", 0)))
                output_m = Decimal(str(price_data.get("output_mtok", 0)))

                new_prices[model_id] = {
                    "input":  input_m / M_TOK,
                    "output": output_m / M_TOK
                }
        
        if new_prices:
            CURRENT_PRICING.update(new_prices)
            PRICING_VERSION = datetime.now(timezone.utc)
            logger.info(f"Pricing updated from remote for {len(new_prices)} models.")
            
    except Exception as e:
        logger.warning(f"Live pricing fetch failed: {e}. Using current state.")    
        

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> tuple[Decimal, datetime]:
    """Calculates cost and returns the version timestamp used."""
    pricing = CURRENT_PRICING.get(model) or FALLBACK_PRICING.get(model)
    
    if pricing is None:
        raise ValueError(f"Unknown model identifier: {model}")

    cost = (Decimal(input_tokens) * pricing["input"]) + (Decimal(output_tokens) * pricing["output"])
    return cost, PRICING_VERSION
