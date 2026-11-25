"""Deterministic financial scale, unit, and number normalization using decimal.Decimal.

Strictly adheres to:
- No binary float arithmetic (Decimal only).
- Standard Indian financial scales: Crore, Lakh, Thousand, Rupees/Units.
- International scales: Million, Billion.
- Parenthetical negative notation: (123.45) -> -123.45.
- Indian numbering system comma parsing: 1,23,456.78.
- Rounding: ROUND_HALF_UP to 4 decimal places internal, 2 decimal places display.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, Tuple


# Regex for cleaning currency symbols, spaces, and commas
_CLEAN_NUM_PATTERN = re.compile(r"[₹$€£\s]")
_PAREN_NEG_PATTERN = re.compile(r"^\s*\(\s*([0-9.,]+)\s*\)\s*$")
_MINUS_PATTERN = re.compile(r"^\s*[-–—]\s*([0-9.,]+)\s*$")

# Decimal quantizers
FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")


class FinancialNormalizer:
    """Provides pure deterministic parsing and scale normalization for financial numbers."""

    # Multipliers relative to CRORE (base unit for Indian financial comparisons)
    # 1 Crore = 10,000,000
    SCALE_TO_CRORE_MULTIPLIER = {
        "CRORE": Decimal("1.0"),
        "CRORES": Decimal("1.0"),
        "CR": Decimal("1.0"),
        "LAKH": Decimal("0.01"),          # 1 Lakh = 0.01 Crore (100,000 / 10,000,000)
        "LAKHS": Decimal("0.01"),
        "LAC": Decimal("0.01"),
        "LACS": Decimal("0.01"),
        "THOUSAND": Decimal("0.0001"),    # 1 Thousand = 0.0001 Crore (1,000 / 10,000,000)
        "THOUSANDS": Decimal("0.0001"),
        "K": Decimal("0.0001"),
        "MILLION": Decimal("0.1"),        # 1 Million = 0.1 Crore (1,000,000 / 10,000,000)
        "MILLIONS": Decimal("0.1"),
        "MN": Decimal("0.1"),
        "BILLION": Decimal("100.0"),      # 1 Billion = 100 Crores (1,000,000,000 / 10,000,000)
        "BILLIONS": Decimal("100.0"),
        "BN": Decimal("100.0"),
        "UNITS": Decimal("0.0000001"),    # 1 Rupee = 1e-7 Crore
        "RUPEES": Decimal("0.0000001"),
        "INR": Decimal("0.0000001"),
    }

    @classmethod
    def parse_raw_number(
        cls,
        raw_val: str,
        allow_dash_as_zero: bool = False,
    ) -> Optional[Decimal]:
        """Safely parse a raw financial text value into a Decimal.
        
        Strict distinctions:
        - Explicitly disclosed numeric zero ('0', '0.0', '0.00', 'zero', '₹0') -> Decimal('0.0000').
        - Blank or whitespace -> None (missing/unavailable).
        - 'nil', 'NIL', 'N/A', 'NA', 'none', 'null' -> None (missing/unavailable, NOT zero).
        - '-' or '—' -> Decimal('0.0000') ONLY if allow_dash_as_zero is True (due to explicit document convention).
          Otherwise None (missing/uncertain, NOT zero).
        - Parentheses for negative numbers: '(1,234.50)' -> Decimal('-1234.50').
        - Minus signs: '-1,234.50' or '— 1,234.50' -> Decimal('-1234.50').
        - Commas and currency symbols: '₹ 1,23,456.78' -> Decimal('123456.78').
        - Returns None if not a valid number.
        """
        if not raw_val:
            return None

        val_str = raw_val.strip()
        if not val_str:
            return None

        val_lower = val_str.lower()
        # Explicit missing / not applicable tokens -> never silently convert to zero
        if val_lower in ("nil", "none", "null", "n.a.", "na", "n/a", "not disclosed", "unavailable"):
            return None

        # Dash handling: only zero if explicit document convention permits
        if val_str in ("-", "—", "–"):
            if allow_dash_as_zero:
                return Decimal("0.0000")
            return None

        # Explicit textual zero
        if val_lower == "zero":
            return Decimal("0.0000")

        # 1. Normalize line breaks around internal commas (e.g. "10,\n500.50" -> "10,500.50")
        val_str = re.sub(r"(?<=\d),\s*\n\s*(?=\d)", ",", val_str)

        # 2. Strip note references and audit qualifiers before inspecting numbers
        # e.g. [Note 4], (Refer Note 2), (Audited), (Unaudited), (Provisional)
        cleaned_qualifiers = re.sub(r"\[(?:notes?|ref)?\s*\d+\]", "", val_str, flags=re.IGNORECASE)
        cleaned_qualifiers = re.sub(r"\((?:refer\s+)?notes?\s*\d+\)", "", cleaned_qualifiers, flags=re.IGNORECASE)
        cleaned_qualifiers = re.sub(r"\((?:audited|unaudited|provisional|restated|revised)\)", "", cleaned_qualifiers, flags=re.IGNORECASE)
        cleaned_qualifiers = re.sub(r"\b(?:audited|unaudited|provisional|restated|revised)\b", "", cleaned_qualifiers, flags=re.IGNORECASE)

        # 3. Check for multiple distinct numbers: reject ambiguous cells (never concatenate distinct figures)
        # Isolate all distinct numeric sequences separated by whitespace, line breaks, or delimiters
        num_tokens = re.findall(
            r"(?:^|[\s/\\|])([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)(?:$|[\s/\\|])",
            cleaned_qualifiers
        )
        if len(num_tokens) > 1:
            # Ambiguous multi-number cell: never concatenate, reject safely
            return None

        # 4. Collapse internal whitespace/line breaks (e.g. "( 1,234.50\n)" -> "( 1,234.50 )")
        val_str = re.sub(r"\s+", " ", cleaned_qualifiers).strip()

        is_negative = False

        # Check for parentheses: (123.45)
        paren_match = _PAREN_NEG_PATTERN.match(val_str)
        if paren_match:
            is_negative = True
            val_str = paren_match.group(1)
        else:
            # Check for leading minus or dash: - 123.45
            minus_match = _MINUS_PATTERN.match(val_str)
            if minus_match:
                is_negative = True
                val_str = minus_match.group(1)

        # Strip currency symbols and whitespace
        cleaned = _CLEAN_NUM_PATTERN.sub("", val_str)
        # Strip all commas (works for both 1,23,456 and 123,456)
        cleaned = cleaned.replace(",", "")

        # Handle trailing negative sign (e.g. 123.45-)
        if cleaned.endswith("-"):
            is_negative = True
            cleaned = cleaned[:-1]

        if not cleaned:
            return None

        try:
            num = Decimal(cleaned)
            if num == Decimal("0"):
                return Decimal("0.0000")
            if is_negative:
                num = -abs(num)
            return num.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return None

    @classmethod
    def normalize_value(
        cls,
        raw_number: Optional[Decimal],
        currency: Optional[str],
        scale: Optional[str],
        metric_key: str = "",
    ) -> Tuple[Optional[Decimal], str, str, str]:
        """Normalize a financial value preserving original currency and scale.
        
        Rules:
        - INR values may be normalized to INR crore when scale is known.
        - Foreign currencies (e.g. USD, EUR) are preserved; never relabeled as INR; no unauthorized FX conversion.
        - Unknown currency or scale remains UNKNOWN.
        - EPS and per-unit metrics retain per-share denomination without scale multiplication.
        
        Returns:
            (normalized_amount, normalized_currency, normalized_scale, normalized_unit)
        """
        norm_curr = (currency.strip().upper() if currency else "UNKNOWN")
        norm_scale = (scale.strip().upper() if scale else "UNKNOWN")

        if raw_number is None:
            unit_str = f"{norm_curr}_{norm_scale}" if norm_scale != "UNKNOWN" else f"{norm_curr}_UNKNOWN_SCALE"
            return None, norm_curr, norm_scale, unit_str

        metric_upper = metric_key.upper()

        # Special Case: Per-share items are reported per share in currency units, not Crores
        if metric_upper in ("EPS", "BASIC_EPS", "DILUTED_EPS", "DIVIDEND_PER_SHARE"):
            per_share_unit = f"{norm_curr}/share" if norm_curr != "UNKNOWN" else "INR/share"
            return raw_number.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP), norm_curr, "PER_SHARE", per_share_unit

        # Scale is unknown: preserve raw number, cannot assume Crore or Thousand
        if norm_scale in ("UNKNOWN", "", "NONE"):
            return raw_number.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP), norm_curr, "UNKNOWN", f"{norm_curr}_UNKNOWN_SCALE"

        # Foreign currency: preserve currency and scale, no unauthorized FX conversion to INR or Crore
        if norm_curr != "INR":
            return raw_number.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP), norm_curr, norm_scale, f"{norm_curr}_{norm_scale}"

        # INR with known scale: normalize to INR_CRORE using deterministic multiplier
        multiplier = cls.SCALE_TO_CRORE_MULTIPLIER.get(norm_scale)
        if multiplier is None:
            return raw_number.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP), "INR", "UNKNOWN", "INR_UNKNOWN_SCALE"

        normalized = (raw_number * multiplier).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        return normalized, "INR", "CRORE", "INR_CRORE"

    @classmethod
    def normalize_to_crore(
        cls,
        raw_number: Decimal,
        scale: str,
        metric_key: str = "",
    ) -> Tuple[Decimal, str]:
        """Convert a parsed Decimal number to INR_CRORE using deterministic multipliers (backward compatible)."""
        norm_amt, _, _, norm_unit = cls.normalize_value(
            raw_number=raw_number,
            currency="INR",
            scale=scale,
            metric_key=metric_key,
        )
        return (norm_amt if norm_amt is not None else raw_number), norm_unit

    @classmethod
    def format_display_amount(cls, amount: Optional[Decimal], unit: str = "INR_CRORE") -> str:
        """Format a Decimal for user-facing display with 2 decimal places and unit suffix."""
        if amount is None:
            return "Not Disclosed"

        rounded = amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        is_neg = rounded < Decimal("0")
        abs_rounded = abs(rounded)

        # Split integer and fractional parts
        parts = f"{abs_rounded:.2f}".split(".")
        int_part = parts[0]
        dec_part = parts[1]

        # Indian numbering grouping if INR / INR_CRORE
        if unit.startswith("INR"):
            if len(int_part) > 3:
                last3 = int_part[-3:]
                remaining = int_part[:-3]
                groups = []
                while remaining:
                    groups.insert(0, remaining[-2:])
                    remaining = remaining[:-2]
                int_formatted = ",".join(groups) + "," + last3
            else:
                int_formatted = int_part
            prefix = "-₹" if is_neg else "₹"
        else:
            # Standard 3-digit comma grouping for foreign/unknown currencies
            try:
                int_formatted = f"{int(int_part):,}"
            except ValueError:
                int_formatted = int_part
            curr_sym = "$" if unit.startswith("USD") else ("€" if unit.startswith("EUR") else "£" if unit.startswith("GBP") else "")
            prefix = f"-{curr_sym}" if is_neg else curr_sym

        formatted = f"{prefix}{int_formatted}.{dec_part}"
        if unit == "INR_CRORE":
            return f"{formatted} Cr"
        elif unit in ("INR", "INR/share"):
            return f"{formatted}/share" if unit == "INR/share" else formatted
        elif unit.endswith("/share"):
            return f"{formatted}/share"
        else:
            return f"{formatted} ({unit})"
