# app/core/tax.py

from __future__ import annotations

from typing import Any


GST = "GST"
VAT = "VAT"

VALID_TAX_TYPES = {GST, VAT}


# =========================================================
# MONEY
# =========================================================

def round_money(
    value: float | int | None,
    decimal_places: int = 2,
) -> float:
    try:
        return round(float(value or 0), decimal_places)
    except (TypeError, ValueError):
        return 0.0


# =========================================================
# NORMALIZE TAX TYPE
# =========================================================

def normalize_tax_type(
    tax_type: Any,
    default: str = GST,
) -> str:
    """
    Normalize tax type.

    Only GST and VAT are supported.

    IMPORTANT:
    Do not silently default a valid-looking missing value to VAT.
    Application-level default is GST unless explicitly configured.
    """

    if tax_type is None:
        return default

    value = str(tax_type).strip().upper()

    if value in VALID_TAX_TYPES:
        return value

    return default


# =========================================================
# COUNTRY -> DEFAULT TAX TYPE
# =========================================================

def get_tax_type_from_country(
    country: str | None,
) -> str:
    """
    Country is ONLY a defaulting mechanism.

    India -> GST
    Everything else -> VAT
    """

    if country and str(country).strip().lower() == "india":
        return GST

    return VAT


# =========================================================
# BRANCH TAX TYPE
# =========================================================

async def resolve_branch_tax_type(
    db,
    branch_id: int,
) -> str:
    """
    Branch.tax_type is authoritative.

    Country is used only if the branch has no tax_type.
    """

    from app.accounts.branch.model import Branch

    branch = await db.get(
        Branch,
        branch_id,
    )

    if not branch:
        return GST

    branch_tax_type = getattr(
        branch,
        "tax_type",
        None,
    )

    if branch_tax_type:
        return normalize_tax_type(
            branch_tax_type,
            default=get_tax_type_from_country(
                getattr(branch, "country", None)
            ),
        )

    return get_tax_type_from_country(
        getattr(branch, "country", None)
    )


# =========================================================
# GENERIC TAX TYPE RESOLUTION
# =========================================================

def resolve_tax_type(
    *,
    stored_tax_type: str | None = None,
    branch_tax_type: str | None = None,
    country: str | None = None,
) -> str:
    """
    Resolve tax type.

    Priority:

        1. branch_tax_type
        2. stored_tax_type
        3. country
        4. GST

    NOTE:
    For billing we will normally pass only branch_tax_type.
    """

    if branch_tax_type:
        return normalize_tax_type(
            branch_tax_type,
            default=GST,
        )

    if stored_tax_type:
        return normalize_tax_type(
            stored_tax_type,
            default=GST,
        )

    if country:
        return get_tax_type_from_country(
            country
        )

    return GST


# =========================================================
# TAX CALCULATION
# =========================================================

def calculate_tax_amounts(
    *,
    taxable_amount: float,
    tax_rate: float,
    tax_type: str,
    decimal_places: int = 2,
) -> dict:
    """
    Calculate GST or VAT.

    GST:
        total tax rate = tax_rate
        CGST = tax_rate / 2
        SGST = tax_rate / 2

    VAT:
        VAT = tax_rate
        CGST = 0
        SGST = 0
    """

    taxable_amount = round_money(
        taxable_amount,
        decimal_places,
    )

    tax_rate = max(
        round_money(
            tax_rate,
            decimal_places,
        ),
        0.0,
    )

    tax_type = normalize_tax_type(
        tax_type,
        default=GST,
    )

    # -----------------------------------------------------
    # VAT
    # -----------------------------------------------------

    if tax_type == VAT:

        vat_rate = tax_rate

        vat_amount = round_money(
            taxable_amount * vat_rate / 100,
            decimal_places,
        )

        return {
            "tax_type": VAT,

            "tax_rate": tax_rate,

            "cgst_rate": 0.0,
            "cgst_amount": 0.0,

            "sgst_rate": 0.0,
            "sgst_amount": 0.0,

            "vat_rate": vat_rate,
            "vat_amount": vat_amount,

            "tax_total": vat_amount,
        }

    # -----------------------------------------------------
    # GST
    # -----------------------------------------------------

    cgst_rate = round_money(
        tax_rate / 2,
        decimal_places,
    )

    sgst_rate = round_money(
        tax_rate - cgst_rate,
        decimal_places,
    )

    cgst_amount = round_money(
        taxable_amount * cgst_rate / 100,
        decimal_places,
    )

    sgst_amount = round_money(
        taxable_amount * sgst_rate / 100,
        decimal_places,
    )

    tax_total = round_money(
        cgst_amount + sgst_amount,
        decimal_places,
    )

    return {
        "tax_type": GST,

        "tax_rate": tax_rate,

        "cgst_rate": cgst_rate,
        "cgst_amount": cgst_amount,

        "sgst_rate": sgst_rate,
        "sgst_amount": sgst_amount,

        "vat_rate": 0.0,
        "vat_amount": 0.0,

        "tax_total": tax_total,
    }


# =========================================================
# BRANCH TAX CONFIG FOR PRICING
# =========================================================

def get_branch_tax_config(
    *,
    country: str | None,
    tax_rate: float,
    decimal_places: int = 2,
    tax_type: str | None = None,
) -> dict:
    """
    Build pricing tax configuration.

    IMPORTANT:
    If tax_type is supplied, it wins over country.
    """

    effective_tax_type = resolve_tax_type(
        branch_tax_type=tax_type,
        country=country,
    )

    return calculate_tax_amounts(
        taxable_amount=0.0,
        tax_rate=tax_rate,
        tax_type=effective_tax_type,
        decimal_places=decimal_places,
    )