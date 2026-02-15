"""FX Rate Stub Connector.

Provides simulated foreign exchange rate data for demo purposes.
Useful for multi-currency contracts where COLA or pricing adjustments
are tied to exchange rates.
"""

import logging
import math
import random
from datetime import date, timedelta
from decimal import Decimal

from app.connectors.base import (
    ConnectorResult,
    DataQuality,
    FXConnector,
    FXRate,
)

logger = logging.getLogger(__name__)


# Base exchange rates (approximate real rates as of early 2025)
BASE_RATES = {
    ("EUR", "USD"): Decimal("1.08"),
    ("EUR", "GBP"): Decimal("0.86"),
    ("EUR", "CHF"): Decimal("0.94"),
    ("EUR", "PLN"): Decimal("4.32"),
    ("EUR", "CZK"): Decimal("25.10"),
    ("EUR", "HUF"): Decimal("395.00"),
    ("EUR", "RON"): Decimal("4.98"),
    ("USD", "EUR"): Decimal("0.93"),
    ("USD", "GBP"): Decimal("0.80"),
    ("USD", "JPY"): Decimal("149.50"),
    ("USD", "CHF"): Decimal("0.87"),
    ("USD", "CAD"): Decimal("1.36"),
    ("USD", "AUD"): Decimal("1.54"),
    ("GBP", "EUR"): Decimal("1.16"),
    ("GBP", "USD"): Decimal("1.25"),
}

# Volatility parameters (annualized)
VOLATILITY = {
    ("EUR", "USD"): 0.08,
    ("EUR", "GBP"): 0.07,
    ("EUR", "CHF"): 0.05,
    ("EUR", "PLN"): 0.10,
    ("EUR", "CZK"): 0.06,
    ("EUR", "HUF"): 0.12,
    ("EUR", "RON"): 0.08,
    ("USD", "EUR"): 0.08,
    ("USD", "GBP"): 0.09,
    ("USD", "JPY"): 0.10,
    ("USD", "CHF"): 0.07,
    ("USD", "CAD"): 0.06,
    ("USD", "AUD"): 0.09,
    ("GBP", "EUR"): 0.07,
    ("GBP", "USD"): 0.09,
}


class FXRateStubConnector(FXConnector):
    """Stub FX rate connector for demo purposes."""

    connector_name = "FX Rates (Stub)"
    is_stub = True

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._seed = config.get("seed", 42) if config else 42
        random.seed(self._seed)

    async def connect(self) -> bool:
        """Simulate connection."""
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    async def health_check(self) -> ConnectorResult:
        """Return healthy status."""
        return ConnectorResult(
            success=True,
            data={"status": "healthy", "pairs_supported": len(BASE_RATES)},
            quality=DataQuality.SIMULATED,
            source="FX Rates Stub",
        )

    async def get_rate(
        self,
        base_currency: str,
        target_currency: str,
        rate_date: date | None = None,
    ) -> ConnectorResult:
        """Get exchange rate for a currency pair.

        Args:
            base_currency: Base currency code (e.g., "EUR").
            target_currency: Target currency code (e.g., "USD").
            rate_date: Date for rate (None = today).

        Returns:
            ConnectorResult with FXRate.
        """
        rate_date = rate_date or date.today()
        pair = (base_currency.upper(), target_currency.upper())

        base_rate = BASE_RATES.get(pair)
        if base_rate is None:
            # Try inverse
            inverse_pair = (target_currency.upper(), base_currency.upper())
            inverse_rate = BASE_RATES.get(inverse_pair)
            if inverse_rate:
                base_rate = Decimal("1") / inverse_rate
            else:
                return ConnectorResult(
                    success=False,
                    error=f"Currency pair not supported: {base_currency}/{target_currency}",
                    source="FX Rates Stub",
                )

        # Generate rate with realistic daily movement
        rate = self._generate_rate(base_rate, pair, rate_date)

        fx_rate = FXRate(
            base_currency=base_currency.upper(),
            target_currency=target_currency.upper(),
            rate=rate,
            rate_date=rate_date,
            source="FX Rates Stub",
        )

        return ConnectorResult(
            success=True,
            data=fx_rate,
            quality=DataQuality.SIMULATED,
            source="FX Rates Stub",
        )

    async def get_rates_history(
        self,
        base_currency: str,
        target_currency: str,
        start_date: date,
        end_date: date,
    ) -> ConnectorResult:
        """Get historical exchange rates.

        Args:
            base_currency: Base currency code.
            target_currency: Target currency code.
            start_date: Start date.
            end_date: End date.

        Returns:
            ConnectorResult with list of FXRate.
        """
        pair = (base_currency.upper(), target_currency.upper())

        base_rate = BASE_RATES.get(pair)
        if base_rate is None:
            inverse_pair = (target_currency.upper(), base_currency.upper())
            inverse_rate = BASE_RATES.get(inverse_pair)
            if inverse_rate:
                base_rate = Decimal("1") / inverse_rate
            else:
                return ConnectorResult(
                    success=False,
                    error=f"Currency pair not supported: {base_currency}/{target_currency}",
                    source="FX Rates Stub",
                )

        rates = []
        current_date = start_date

        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:
                rate = self._generate_rate(base_rate, pair, current_date)
                fx_rate = FXRate(
                    base_currency=base_currency.upper(),
                    target_currency=target_currency.upper(),
                    rate=rate,
                    rate_date=current_date,
                    source="FX Rates Stub",
                )
                rates.append(fx_rate)

            current_date += timedelta(days=1)

        # Calculate summary statistics
        rate_values = [float(r.rate) for r in rates]
        summary = {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "trading_days": len(rates),
            "average_rate": round(sum(rate_values) / len(rate_values), 4) if rates else 0,
            "min_rate": round(min(rate_values), 4) if rates else 0,
            "max_rate": round(max(rate_values), 4) if rates else 0,
            "volatility_pct": round(
                (max(rate_values) - min(rate_values)) / (sum(rate_values) / len(rate_values)) * 100, 2
            ) if rates else 0,
        }

        return ConnectorResult(
            success=True,
            data={"rates": rates, "summary": summary},
            quality=DataQuality.SIMULATED,
            source="FX Rates Stub",
            metadata=summary,
        )

    async def get_cola_adjustment(
        self,
        base_currency: str,
        target_currency: str,
        contract_rate: Decimal,
        current_date: date | None = None,
    ) -> ConnectorResult:
        """Calculate COLA (Cost of Living Adjustment) based on FX movement.

        Args:
            base_currency: Contract base currency.
            target_currency: Payment currency.
            contract_rate: Exchange rate at contract signing.
            current_date: Date for current rate (None = today).

        Returns:
            ConnectorResult with adjustment calculation.
        """
        current_date = current_date or date.today()

        # Get current rate
        current_result = await self.get_rate(base_currency, target_currency, current_date)
        if not current_result.success:
            return current_result

        current_rate = current_result.data.rate

        # Calculate adjustment
        contract_rate_dec = Decimal(str(contract_rate)) if not isinstance(contract_rate, Decimal) else contract_rate
        rate_change = (current_rate - contract_rate_dec) / contract_rate_dec
        adjustment_pct = float(rate_change) * 100

        # Determine if adjustment threshold is met (typically 2-3%)
        threshold = 2.0  # 2% threshold
        adjustment_applicable = abs(adjustment_pct) >= threshold

        adjustment_data = {
            "base_currency": base_currency,
            "target_currency": target_currency,
            "contract_rate": float(contract_rate),
            "current_rate": float(current_rate),
            "rate_change_pct": round(adjustment_pct, 2),
            "threshold_pct": threshold,
            "adjustment_applicable": adjustment_applicable,
            "adjustment_direction": "increase" if adjustment_pct > 0 else "decrease",
            "effective_date": current_date.isoformat(),
        }

        if adjustment_applicable:
            adjustment_data["notes"] = (
                f"FX movement of {abs(adjustment_pct):.1f}% exceeds {threshold}% threshold. "
                f"Price adjustment {'increase' if adjustment_pct > 0 else 'decrease'} applicable."
            )
        else:
            adjustment_data["notes"] = (
                f"FX movement of {abs(adjustment_pct):.1f}% within {threshold}% threshold. "
                "No adjustment required."
            )

        return ConnectorResult(
            success=True,
            data=adjustment_data,
            quality=DataQuality.SIMULATED,
            source="FX Rates Stub",
        )

    def _generate_rate(
        self,
        base_rate: Decimal,
        pair: tuple[str, str],
        rate_date: date,
    ) -> Decimal:
        """Generate realistic exchange rate with random walk.

        Uses geometric Brownian motion model for realistic FX movement.
        """
        # Get volatility for this pair
        vol = VOLATILITY.get(pair, 0.08)

        # Days from a reference date for consistent random walk
        ref_date = date(2024, 1, 1)
        days_from_ref = (rate_date - ref_date).days

        # Seed based on pair and date for reproducibility
        seed = hash(f"{pair[0]}{pair[1]}{rate_date.isoformat()}")
        rng = random.Random(seed)

        # Simulate random walk
        daily_vol = vol / math.sqrt(252)  # Annualized to daily
        cumulative_return = 0.0

        for day in range(days_from_ref):
            daily_return = rng.gauss(0, daily_vol)
            cumulative_return += daily_return

        # Apply cumulative return to base rate
        rate = float(base_rate) * math.exp(cumulative_return)

        # Round to 4 decimal places
        return Decimal(str(round(rate, 4)))


def get_fx_stub() -> FXRateStubConnector:
    """Get FX rate stub connector instance."""
    return FXRateStubConnector()
