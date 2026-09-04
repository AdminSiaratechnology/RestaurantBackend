# app/utils/currency_formatter.py

from decimal import Decimal
from typing import Union, Optional, Tuple, Dict, Any

import os

CURRENCY_MAP: Dict[str, Dict[str, Any]] = {
    "USD": {"symbol": "$", "name": "US Dollar"},
    "INR": {"symbol": "₹", "name": "Indian Rupee"},
    "AED": {"symbol": "د.إ", "name": "UAE Dirham"},
    "EUR": {"symbol": "€", "name": "Euro"},
    "GBP": {"symbol": "£", "name": "British Pound"},
    "CAD": {"symbol": "CA$", "name": "Canadian Dollar"},
    "AUD": {"symbol": "A$", "name": "Australian Dollar"},
    "SGD": {"symbol": "S$", "name": "Singapore Dollar"},
    "SAR": {"symbol": "SR", "name": "Saudi Riyal"},
    "QAR": {"symbol": "QR", "name": "Qatari Riyal"},
    "OMR": {"symbol": "OMR", "name": "Omani Rial"},
    "KWD": {"symbol": "KD", "name": "Kuwaiti Dinar"},
    "BHD": {"symbol": "BD", "name": "Bahraini Dinar"},
    "JPY": {"symbol": "¥", "name": "Japanese Yen"},
    "CNY": {"symbol": "¥", "name": "Chinese Yuan"},
}


def get_omr_symbol_img_path() -> Optional[str]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "..", "..", "public", "omr_symbol.png"),
        os.path.join(os.getcwd(), "public", "omr_symbol.png"),
        os.path.join(os.getcwd(), "RMSbackend", "RestaurantBackend", "public", "omr_symbol.png"),
        os.path.join(base_dir, "..", "assets", "omr_symbol.png"),
        os.path.join(base_dir, "..", "..", "app", "assets", "omr_symbol.png"),
        os.path.join(os.getcwd(), "app", "assets", "omr_symbol.png"),
        os.path.join(os.getcwd(), "RMSbackend", "RestaurantBackend", "app", "assets", "omr_symbol.png"),
    ]
    for candidate in candidates:
        abs_p = os.path.abspath(candidate)
        if os.path.exists(abs_p):
            return abs_p
    return None


def get_currency_symbol(currency_code: str = "INR", custom_symbol: Optional[str] = None) -> str:
    if custom_symbol and str(custom_symbol).strip():
        return str(custom_symbol).strip()
    code = (currency_code or "INR").upper().strip()
    return CURRENCY_MAP.get(code, {}).get("symbol", code)


def get_excel_currency_num_format(currency_symbol: str = "₹", decimal_places: int = 2) -> str:
    symbol = get_currency_symbol(custom_symbol=currency_symbol)
    places = max(0, int(decimal_places if decimal_places is not None else 2))
    if places == 0:
        return f'"{symbol}"#,##0'
    else:
        zeros = "0" * places
        return f'"{symbol}"#,##0.{zeros}'


def format_currency(
    amount: Union[int, float, Decimal, str, None],
    currency_symbol: str = "₹",
    decimal_places: int = 2,
    currency_code: str = "INR",
    include_space: bool = False,
    for_pdf: bool = False,
) -> str:
    """
    Format a monetary value dynamically according to branch settings.
    - safely handles None / empty / invalid input
    - applies branch decimal precision (0, 2, 3, etc.)
    - prefixes branch currency symbol (e.g. $500.00, ₹500, د.إ500.000)
    - for OMR in PDF, uses official inline symbol graphic
    """
    if amount is None:
        amount_float = 0.0
    else:
        try:
            amount_float = float(amount)
        except (ValueError, TypeError):
            amount_float = 0.0

    code = (currency_code or "").upper().strip()
    symbol = get_currency_symbol(currency_code=code, custom_symbol=currency_symbol)
    places = max(0, int(decimal_places if decimal_places is not None else 2))

    if places == 0:
        formatted_num = f"{round(amount_float):,}"
    else:
        formatted_num = f"{amount_float:,.{places}f}"

    is_omr = code == "OMR" or symbol == "OMR" or (currency_symbol and str(currency_symbol).strip().upper() == "OMR")

    if is_omr and for_pdf:
        omr_img_path = get_omr_symbol_img_path()
        if omr_img_path:
            return f'<img src="{omr_img_path}" width="12" height="7" valign="middle"/> {formatted_num}'

    space = " " if include_space or is_omr or (symbol and (len(symbol) > 1 or symbol.isalpha())) else ""
    return f"{symbol}{space}{formatted_num}"


def get_branch_currency_settings(branch: Any) -> Tuple[str, str, int]:
    """
    Extract (currency_code, currency_symbol, decimal_places) from a Branch model instance,
    dictionary, or SQLAlchemy object.
    """
    if not branch:
        return ("INR", "₹", 2)

    if isinstance(branch, dict):
        country = str(branch.get("country") or "").strip().lower()
        code = str(branch.get("currency") or branch.get("currency_code") or ("OMR" if country == "oman" else "INR")).upper()
        sym = branch.get("currency_symbol") or get_currency_symbol(currency_code=code)
        dec = branch.get("decimal_places", 3 if (code == "OMR" or country == "oman") else 2)
    else:
        country = str(getattr(branch, "country", "") or "").strip().lower()
        code = str(getattr(branch, "currency", None) or getattr(branch, "currency_code", None) or ("OMR" if country == "oman" else "INR")).upper()
        sym = getattr(branch, "currency_symbol", None) or get_currency_symbol(currency_code=code)
        dec = getattr(branch, "decimal_places", None)
        if dec is None:
            dec = 3 if (code == "OMR" or country == "oman") else 2

    try:
        dec = int(dec if dec is not None else (3 if code == "OMR" else 2))
    except (ValueError, TypeError):
        dec = 3 if code == "OMR" else 2

    return (code, sym, dec)


async def get_branch_currency_settings_from_db(branch_id: int, db) -> Tuple[str, str, int]:
    """
    Independently fetch branch currency settings from DB given branch_id.
    Returns (currency_code, currency_symbol, decimal_places).
    """
    if not branch_id or not db:
        return ("INR", "₹", 2)

    try:
        from sqlalchemy import select
        from app.accounts.branch.model import Branch

        result = await db.execute(select(Branch).where(Branch.id == branch_id))
        branch = result.scalar_one_or_none()
        if branch:
            return get_branch_currency_settings(branch)
    except Exception:
        pass

    return ("INR", "₹", 2)
