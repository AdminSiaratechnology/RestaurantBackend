# =========================================================
# app/core/tax.py
# =========================================================


def get_tax_type_from_country(
    country: str | None,
) -> str:
    """
    India -> GST
    Every other country -> VAT
    """

    if not country:
        return "VAT"

    normalized_country = country.strip().lower()

    if normalized_country == "india":
        return "GST"

    return "VAT"


def get_branch_tax_config(
    tax_type: str,
    tax_rate: float,
) -> dict:
    """
    GST:
        Total Tax = tax_rate
        CGST = tax_rate / 2
        SGST = tax_rate / 2

    VAT:
        Total Tax = tax_rate
        CGST = 0
        SGST = 0
    """

    tax_type = (tax_type or "VAT").strip().upper()

    # =====================================================
    # GST
    # =====================================================

    if tax_type == "GST":

        half_tax = round(tax_rate / 2, 2)

        return {
            "tax_type": "GST",
            "tax_rate": round(tax_rate, 2),
            "cgst_rate": half_tax,
            "sgst_rate": half_tax,
        }

    # =====================================================
    # VAT
    # =====================================================

    return {
        "tax_type": "VAT",
        "tax_rate": round(tax_rate, 2),
        "cgst_rate": 0.0,
        "sgst_rate": 0.0,
    }