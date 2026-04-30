"""Whitelist and validate the JSON documents stored for clients and reports.

Only known keys are kept. Identifier fields are limited to their last four
digits so a full SSN or account number can never be stored by mistake.
"""

import re

LAST4 = re.compile(r"^\d{0,4}$")
ISO_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})?$")
QUARTERS = ("Q1", "Q2", "Q3", "Q4")
MAX_ACCOUNTS = 25


class Invalid(ValueError):
    def __init__(self, fields):
        super().__init__("invalid fields")
        self.fields = fields


def _text(value, limit):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"must be text of at most {limit} characters")
    return value.strip()


def _amount(value):
    """Blank stays blank so the form can show an empty input; otherwise a number."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        raise ValueError("must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("must be a number") from None
    if number != number or abs(number) > 1e12:
        raise ValueError("is out of range")
    return number


def _pattern(value, pattern, message):
    value = _text(value, 16)
    if not pattern.match(value):
        raise ValueError(message)
    return value


def _last4(value):
    return _pattern(value, LAST4, "must be at most the last 4 digits")


def _age(value):
    if value in (None, ""):
        return ""
    try:
        age = int(value)
    except (TypeError, ValueError):
        raise ValueError("must be a whole number") from None
    if not 0 <= age <= 130:
        raise ValueError("is out of range")
    return age


def _accounts(value, fields):
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > MAX_ACCOUNTS:
        raise ValueError(f"must be a list of at most {MAX_ACCOUNTS} accounts")
    cleaned = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each account must be an object")
        cleaned.append(_apply(item, fields))
    return cleaned


def _apply(data, fields):
    clean, errors = {}, {}
    for key, check in fields.items():
        try:
            clean[key] = check(data.get(key))
        except Invalid as exc:
            errors.update({f"{key}.{k}": v for k, v in exc.fields.items()})
        except ValueError as exc:
            errors[key] = str(exc)
    if errors:
        raise Invalid(errors)
    return clean


def _required_name(value):
    name = _text(value, 120)
    if not name:
        raise ValueError("is required")
    return name


ACCOUNT_FIELDS = {
    "type": lambda v: _text(v, 60),
    "acct_num": _last4,
    "rate": _amount,
}
BALANCE_FIELDS = {**ACCOUNT_FIELDS, "balance": _amount, "cash": _amount}

CLIENT_FIELDS = {
    "name_1": _required_name,
    "name_2": lambda v: _text(v, 120),
    "dob_1": lambda v: _pattern(v, ISO_DATE, "must be a YYYY-MM-DD date"),
    "dob_2": lambda v: _pattern(v, ISO_DATE, "must be a YYYY-MM-DD date"),
    "ssn_1": _last4,
    "ssn_2": _last4,
    "age_1": _age,
    "age_2": _age,
    "monthly_salary": _amount,
    "expense_budget": _amount,
    "pr_target": _amount,
    "trust_address": lambda v: _text(v, 200),
    "retirement_accounts_1": lambda v: _accounts(v, ACCOUNT_FIELDS),
    "retirement_accounts_2": lambda v: _accounts(v, ACCOUNT_FIELDS),
    "non_retirement_accounts": lambda v: _accounts(v, ACCOUNT_FIELDS),
    "liabilities": lambda v: _accounts(v, ACCOUNT_FIELDS),
}


def _quarter(value):
    if value in (None, ""):
        return "Q1"
    if value not in QUARTERS:
        raise ValueError("must be one of Q1-Q4")
    return value


def _year(value):
    try:
        year = int(value)
    except (TypeError, ValueError):
        raise ValueError("must be a year") from None
    if not 2000 <= year <= 2100:
        raise ValueError("is out of range")
    return year


REPORT_FIELDS = {
    "quarter": _quarter,
    "year": _year,
    "inflow": _amount,
    "outflow": _amount,
    "private_reserve_target": _amount,
    "private_reserve_balance": _amount,
    "pinnacle_checking": _amount,
    "pinnacle_savings": _amount,
    "schwab_balance": _amount,
    "schwab_cash": _amount,
    "trust_value": _amount,
    "trust_address": lambda v: _text(v, 200),
    "retirement_1": lambda v: _accounts(v, BALANCE_FIELDS),
    "retirement_2": lambda v: _accounts(v, BALANCE_FIELDS),
    "non_retirement": lambda v: _accounts(v, BALANCE_FIELDS),
    "liabilities": lambda v: _accounts(v, BALANCE_FIELDS),
}


def clean_client(data):
    return _apply(data, CLIENT_FIELDS)


def clean_report(data, default_year):
    return _apply({"year": default_year, **data}, REPORT_FIELDS)
