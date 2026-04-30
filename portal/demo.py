"""`flask --app app seed-demo`: fictional households for trying the portal out."""

import click
from flask.cli import with_appcontext

from . import db

HOUSEHOLDS = [
    {
        "client": {
            "name_1": "Dana Whitfield",
            "name_2": "Sam Whitfield",
            "dob_1": "1971-04-02",
            "dob_2": "1973-09-18",
            "age_1": 55,
            "age_2": 53,
            "ssn_1": "0142",
            "ssn_2": "0187",
            "monthly_salary": 15000,
            "expense_budget": 11000,
            "pr_target": "",
            "trust_address": "14 Juniper Lane",
            "retirement_accounts_1": [
                {"type": "401K", "acct_num": "1182"},
                {"type": "Roth IRA", "acct_num": "2290"},
            ],
            "retirement_accounts_2": [{"type": "403b", "acct_num": "7731"}],
            "non_retirement_accounts": [{"type": "Joint Brokerage", "acct_num": "5520"}],
            "liabilities": [{"type": "Mortgage", "acct_num": "9001", "rate": 3.1}],
        },
        "balances": [
            ("Q2", 2026, 41000, [398000, 61000], [118000], [142000, 3800], 672000, [215400]),
            ("Q3", 2026, 48000, [412000, 64500], [121500], [150000, 4000], 685000, [212000]),
        ],
    },
    {
        "client": {
            "name_1": "Priya Raman",
            "dob_1": "1984-01-27",
            "age_1": 42,
            "ssn_1": "0311",
            "monthly_salary": 9200,
            "expense_budget": 6100,
            "pr_target": 40000,
            "trust_address": "8 Alder Court",
            "retirement_accounts_1": [{"type": "SEP IRA", "acct_num": "4410"}],
            "non_retirement_accounts": [{"type": "Money Market", "acct_num": "6620"}],
            "liabilities": [{"type": "Auto Loan", "acct_num": "3307", "rate": 4.9}],
        },
        "balances": [("Q3", 2026, 27500, [184000], [], [36000, 36000], 455000, [18400])],
    },
    {
        "client": {
            "name_1": "Marcus Okafor",
            "name_2": "Elena Okafor",
            "dob_1": "1965-11-03",
            "dob_2": "1967-06-21",
            "age_1": 61,
            "age_2": 59,
            "ssn_1": "0458",
            "ssn_2": "0463",
            "monthly_salary": 21000,
            "expense_budget": 14500,
            "pr_target": "",
            "trust_address": "230 Harbor View Road",
            "retirement_accounts_1": [
                {"type": "Pension", "acct_num": "1009"},
                {"type": "IRA", "acct_num": "1010"},
            ],
            "retirement_accounts_2": [{"type": "401K", "acct_num": "2020"}],
            "non_retirement_accounts": [{"type": "Schwab Brokerage", "acct_num": "3030"}],
            "liabilities": [],
        },
        "balances": [],
    },
]


def _report(client, quarter, year, reserve, ret1, ret2, nonret, trust, liabs):
    def with_balances(accounts, values):
        return [{**a, "balance": v} for a, v in zip(accounts, values, strict=False)]

    expenses = client["expense_budget"]
    nonret_accounts = client.get("non_retirement_accounts", [])
    return {
        "quarter": quarter,
        "year": year,
        "inflow": client["monthly_salary"],
        "outflow": expenses,
        "private_reserve_target": client["pr_target"] or expenses * 6,
        "private_reserve_balance": reserve,
        "pinnacle_checking": 6200,
        "pinnacle_savings": 9100,
        "schwab_balance": 0,
        "schwab_cash": 0,
        "trust_value": trust,
        "trust_address": client["trust_address"],
        "retirement_1": with_balances(client.get("retirement_accounts_1", []), ret1),
        "retirement_2": with_balances(client.get("retirement_accounts_2", []), ret2),
        "non_retirement": [
            {**a, "balance": nonret[0], "cash": nonret[1]} for a in nonret_accounts[:1] if nonret
        ],
        "liabilities": with_balances(client.get("liabilities", []), liabs),
    }


@click.command("seed-demo")
@with_appcontext
def seed_demo():
    """Add three fictional households (skipped if any client exists)."""
    if db.list_clients(year=0):
        click.echo("Clients already exist; demo data not added.")
        return
    for household in HOUSEHOLDS:
        client = household["client"]
        cid = db.create_client(client)
        for quarter, year, *figures in household["balances"]:
            db.create_report(cid, quarter, year, _report(client, quarter, year, *figures))
    click.echo(f"Added {len(HOUSEHOLDS)} demo households.")
