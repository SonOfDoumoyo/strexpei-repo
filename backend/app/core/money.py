"""Money maths. Everything is integer kobo (1 NGN = 100 kobo).

Fee defaults mirror Paystack's published Nigerian pricing (October 2026):

* Local collections: 1.5% + NGN 100, the NGN 100 waived under NGN 2,500,
  capped at NGN 2,000.
* Dedicated virtual accounts (bank transfer to an account number): 1%,
  capped at NGN 300.
* Transfers (payouts): NGN 10 up to NGN 5,000; NGN 25 up to NGN 50,000;
  NGN 50 above that. Stamp duty of NGN 50 on transfers of NGN 10,000+.

All of these are editable by an admin at runtime (platform settings), so a
Paystack price change never needs a deploy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

KOBO_PER_NAIRA = 100


def naira_to_kobo(value: Any) -> int:
    """Converts '1,250.50', 1250.5, Decimal or int naira to kobo."""
    if isinstance(value, bool):
        raise ValueError("Invalid amount")
    if isinstance(value, str):
        value = value.replace(",", "").replace("₦", "").replace("NGN", "").strip()
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid amount") from exc
    if not amount.is_finite():
        raise ValueError("Invalid amount")
    return int((amount * KOBO_PER_NAIRA).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def kobo_to_naira(kobo: int) -> Decimal:
    return (Decimal(kobo) / KOBO_PER_NAIRA).quantize(Decimal("0.01"))


def format_naira(kobo: int, with_kobo: bool | None = None) -> str:
    naira = kobo_to_naira(kobo)
    show_kobo = with_kobo if with_kobo is not None else (kobo % 100 != 0)
    if show_kobo:
        return f"₦{naira:,.2f}"
    return f"₦{int(naira):,}"


def bps_label(bps: int) -> str:
    """50 -> '0.5%'"""
    value = Decimal(bps) / Decimal(100)
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def bps_of(amount_kobo: int, bps: int) -> int:
    """amount * bps / 10_000 rounded half-up to the kobo."""
    return int((Decimal(amount_kobo) * bps / Decimal(10_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class TransferBand:
    up_to_kobo: int | None  # inclusive upper bound, None = no limit
    fee_kobo: int


@dataclass
class FeeSchedule:
    commission_bps: int = 50  # Streixpei commission: 0.5% of disbursed salaries

    checkout_percent_bps: int = 150
    checkout_flat_kobo: int = 100_00
    checkout_flat_waived_below_kobo: int = 2_500_00
    checkout_cap_kobo: int = 2_000_00

    dva_percent_bps: int = 100
    dva_cap_kobo: int = 300_00

    transfer_bands: list[TransferBand] = field(
        default_factory=lambda: [
            TransferBand(5_000_00, 10_00),
            TransferBand(50_000_00, 25_00),
            TransferBand(None, 50_00),
        ]
    )
    stamp_duty_threshold_kobo: int = 10_000_00
    stamp_duty_kobo: int = 50_00

    # ------------------------------------------------------------ factory
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FeeSchedule":
        base = cls()
        if not data:
            return base
        values = asdict(base)
        for key, value in data.items():
            if key == "transfer_bands" and isinstance(value, list):
                values[key] = value
            elif key in values and isinstance(value, int) and not isinstance(value, bool):
                values[key] = value
        bands = [TransferBand(b.get("up_to_kobo"), int(b["fee_kobo"])) for b in values.pop("transfer_bands")]
        bands.sort(key=lambda b: (b.up_to_kobo is None, b.up_to_kobo or 0))
        return cls(transfer_bands=bands, **values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    # --------------------------------------------------------- collections
    def checkout_fee(self, gross_kobo: int) -> int:
        """Paystack's fee on a local card/bank/USSD charge of ``gross_kobo``."""
        if gross_kobo <= 0:
            return 0
        fee = bps_of(gross_kobo, self.checkout_percent_bps)
        if gross_kobo >= self.checkout_flat_waived_below_kobo:
            fee += self.checkout_flat_kobo
        return min(fee, self.checkout_cap_kobo)

    def dva_fee(self, gross_kobo: int) -> int:
        if gross_kobo <= 0:
            return 0
        return min(bps_of(gross_kobo, self.dva_percent_bps), self.dva_cap_kobo)

    def collection_fee(self, gross_kobo: int, channel: str) -> int:
        return self.dva_fee(gross_kobo) if channel == "dva" else self.checkout_fee(gross_kobo)

    def gross_up(self, net_kobo: int, channel: str) -> int:
        """Smallest amount to charge so that, after Paystack's fee, ``net_kobo`` arrives."""
        if net_kobo <= 0:
            return 0
        fee_fn = self.dva_fee if channel == "dva" else self.checkout_fee
        if channel == "dva":
            pct, flat, cap, waived_below = self.dva_percent_bps, 0, self.dva_cap_kobo, 0
        else:
            pct, flat, cap, waived_below = (
                self.checkout_percent_bps,
                self.checkout_flat_kobo,
                self.checkout_cap_kobo,
                self.checkout_flat_waived_below_kobo,
            )
        divisor = Decimal(10_000 - pct)

        def ceil_div(numerator: int) -> int:
            return int((Decimal(numerator) * 10_000 / divisor).to_integral_value(rounding="ROUND_CEILING"))

        def fix_up(candidate: int) -> int:
            candidate = max(candidate, net_kobo)
            while candidate - fee_fn(candidate) < net_kobo:
                candidate += 1
            return candidate

        candidates = [ceil_div(net_kobo + flat), net_kobo + cap]
        no_flat = ceil_div(net_kobo)
        if flat == 0 or no_flat < waived_below:
            candidates.append(no_flat)
        gross = min(fix_up(c) for c in candidates)
        # Step down to the smallest amount that still nets the target.
        while gross - 1 >= net_kobo and (gross - 1) - fee_fn(gross - 1) >= net_kobo:
            gross -= 1
        return gross

    # ------------------------------------------------------------ payouts
    def transfer_fee(self, amount_kobo: int) -> int:
        fee = self.transfer_bands[-1].fee_kobo
        for band in self.transfer_bands:
            if band.up_to_kobo is None or amount_kobo <= band.up_to_kobo:
                fee = band.fee_kobo
                break
        if self.stamp_duty_kobo and amount_kobo >= self.stamp_duty_threshold_kobo:
            fee += self.stamp_duty_kobo
        return fee

    def commission(self, amount_kobo: int) -> int:
        return bps_of(amount_kobo, self.commission_bps)


@dataclass
class PayoutBreakdown:
    salaries_kobo: int = 0
    transfer_fees_kobo: int = 0
    commission_kobo: int = 0

    @property
    def total_kobo(self) -> int:
        return self.salaries_kobo + self.transfer_fees_kobo + self.commission_kobo

    def add(self, amount_kobo: int, fees: FeeSchedule) -> tuple[int, int]:
        fee = fees.transfer_fee(amount_kobo)
        commission = fees.commission(amount_kobo)
        self.salaries_kobo += amount_kobo
        self.transfer_fees_kobo += fee
        self.commission_kobo += commission
        return fee, commission

    def as_dict(self) -> dict[str, int]:
        return {
            "salaries_kobo": self.salaries_kobo,
            "transfer_fees_kobo": self.transfer_fees_kobo,
            "commission_kobo": self.commission_kobo,
            "total_kobo": self.total_kobo,
        }
