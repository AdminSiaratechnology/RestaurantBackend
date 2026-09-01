# app/utils/currency_formatter.py

from decimal import Decimal
from typing import Union, Optional, Tuple, Dict, Any

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
) -> str:
    """
    Format a monetary value dynamically according to branch settings.
    - safely handles None / empty / invalid input
    - applies branch decimal precision (0, 2, 3, etc.)
    - prefixes branch currency symbol (e.g. $500.00, ₹500, د.إ500.000)
    """
    if amount is None:
        amount_float = 0.0
    else:
        try:
            amount_float = float(amount)
        except (ValueError, TypeError):
            amount_float = 0.0

    symbol = get_currency_symbol(currency_code=currency_code, custom_symbol=currency_symbol)
    places = max(0, int(decimal_places if decimal_places is not None else 2))

    if places == 0:
        formatted_num = f"{round(amount_float):,}"
    else:
        formatted_num = f"{amount_float:,.{places}f}"

    space = " " if include_space else ""
    return f"{symbol}{space}{formatted_num}"


def get_branch_currency_settings(branch: Any) -> Tuple[str, str, int]:
    """
    Extract (currency_code, currency_symbol, decimal_places) from a Branch model instance,
    dictionary, or SQLAlchemy object.
    """
    if not branch:
        return ("INR", "₹", 2)

    if isinstance(branch, dict):
        code = str(branch.get("currency") or branch.get("currency_code") or "INR").upper()
        sym = branch.get("currency_symbol") or get_currency_symbol(currency_code=code)
        dec = branch.get("decimal_places", 2)
    else:
        code = str(getattr(branch, "currency", "INR") or getattr(branch, "currency_code", "INR") or "INR").upper()
        sym = getattr(branch, "currency_symbol", None) or get_currency_symbol(currency_code=code)
        dec = getattr(branch, "decimal_places", 2)

    try:
        dec = int(dec if dec is not None else 2)
    except (ValueError, TypeError):
        dec = 2

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
