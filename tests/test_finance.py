import pytest

from portal.finance import fmt_money, household_name, sacs_figures, tcc_totals, to_number


@pytest.mark.parametrize(
    ("raw", "expected"), [("", 0.0), (None, 0.0), ("abc", 0.0), ("1250.5", 1250.5), (7, 7.0)]
)
def test_to_number(raw, expected):
    assert to_number(raw) == expected


def test_fmt_money_rounds_and_groups():
    assert fmt_money("1234567.6") == "$1,234,568"
    assert fmt_money("") == "$0"


def test_household_name():
    assert household_name({"name_1": "Dana"}) == "Dana"
    assert household_name({"name_1": "Dana", "name_2": "Sam"}) == "Dana & Sam"


def test_sacs_excess_and_liquid_assets():
    f = sacs_figures(
        {
            "inflow": 15000,
            "outflow": "11000",
            "private_reserve_balance": "40000",
            "pinnacle_checking": "5000",
            "pinnacle_savings": "",
            "schwab_balance": "90000",
        }
    )
    assert f["excess"] == 4000
    assert f["total_liquid"] == 45000  # Schwab is investments, not liquid


def test_tcc_liabilities_not_subtracted_and_trust_separate():
    client = {"name_1": "Dana", "name_2": "Sam"}
    report = {
        "retirement_1": [{"balance": "100"}, {"balance": ""}],
        "retirement_2": [{"balance": "50"}],
        "non_retirement": [{"balance": "25", "cash": "5"}],
        "trust_value": "400",
        "liabilities": [{"balance": "300"}],
    }
    t = tcc_totals(client, report)
    assert (t["ret1"], t["ret2"], t["nonret"], t["trust"]) == (100, 50, 25, 400)
    assert t["grand"] == 575
    assert t["liab"] == 300


def test_tcc_ignores_spouse_accounts_without_spouse():
    t = tcc_totals({"name_1": "Dana"}, {"retirement_2": [{"balance": "999"}]})
    assert t["ret2"] == 0
