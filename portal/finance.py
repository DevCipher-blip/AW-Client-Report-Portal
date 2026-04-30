"""Report arithmetic, kept apart from the PDF drawing so it can be tested directly."""


def to_number(val):
    """Form fields arrive as strings and are often left blank; treat those as 0."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def fmt_money(val):
    return f"${to_number(val):,.0f}"


def household_name(client):
    if client.get("name_2"):
        return f"{client.get('name_1', '')} & {client['name_2']}"
    return client.get("name_1", "Client")


def sacs_figures(report):
    inflow = to_number(report.get("inflow", 0))
    outflow = to_number(report.get("outflow", 0))
    pr_balance = to_number(report.get("private_reserve_balance", 0))
    checking = to_number(report.get("pinnacle_checking", 0))
    savings = to_number(report.get("pinnacle_savings", 0))
    return {
        "inflow": inflow,
        "outflow": outflow,
        "excess": inflow - outflow,
        "pr_balance": pr_balance,
        "pr_target": to_number(report.get("private_reserve_target", 0)),
        "schwab_balance": to_number(report.get("schwab_balance", 0)),
        "schwab_cash": to_number(report.get("schwab_cash", 0)),
        "pinnacle_checking": checking,
        "pinnacle_savings": savings,
        # Investment accounts are deliberately excluded from liquid assets.
        "total_liquid": pr_balance + checking + savings,
    }


def _sum_balances(accounts):
    return sum(to_number(a.get("balance", 0)) for a in accounts or [])


def tcc_totals(client, report):
    ret1 = _sum_balances(report.get("retirement_1"))
    # A spouse's accounts only count when the client actually has a spouse on file.
    ret2 = _sum_balances(report.get("retirement_2")) if client.get("name_2") else 0.0
    nonret = _sum_balances(report.get("non_retirement"))
    trust = to_number(report.get("trust_value", 0))
    return {
        "ret1": ret1,
        "ret2": ret2,
        "nonret": nonret,
        "trust": trust,
        # Liabilities are reported alongside, never subtracted from, net worth.
        "grand": ret1 + ret2 + nonret + trust,
        "liab": _sum_balances(report.get("liabilities")),
    }
