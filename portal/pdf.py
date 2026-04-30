"""ReportLab drawing for the SACS and TCC client reports."""

import io
import math
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .finance import fmt_money, household_name, sacs_figures, tcc_totals, to_number

DEFAULT_FIRM = "Windbrook Solutions"

BLUE = HexColor("#1B3A6B")
LIGHT_BLUE = HexColor("#2E5FAC")
GREEN = HexColor("#2E7D32")
LIGHT_GREEN = HexColor("#4CAF50")
RED = HexColor("#C62828")
LIGHT_RED = HexColor("#EF5350")
GRAY = HexColor("#F5F5F5")
DARK_GRAY = HexColor("#424242")
WHITE = colors.white
GOLD = HexColor("#C8A951")

W, H = letter


def draw_circle(c, cx, cy, r, fill_color, stroke_color=None, stroke_width=2):
    c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(stroke_width)
        c.circle(cx, cy, r, fill=1, stroke=1)
    else:
        c.circle(cx, cy, r, fill=1, stroke=0)


def draw_arrow(c, x1, y1, x2, y2, color, width=2):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)
    angle = math.atan2(y2 - y1, x2 - x1)
    head = 10
    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - head * math.cos(angle - 0.4), y2 - head * math.sin(angle - 0.4))
    p.lineTo(x2 - head * math.cos(angle + 0.4), y2 - head * math.sin(angle + 0.4))
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def draw_header(c, firm, subtitle, client, report):
    c.setFillColor(BLUE)
    c.rect(0, H - 80, W, 80, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, H - 38, firm)
    c.setFont("Helvetica", 11)
    c.drawString(40, H - 56, subtitle)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(W - 40, H - 38, household_name(client))
    c.setFont("Helvetica", 10)
    c.drawRightString(
        W - 40, H - 56, f"{report.get('quarter', 'Q1')} {report.get('year', datetime.now().year)}"
    )
    c.setFillColor(GOLD)
    c.rect(0, H - 84, W, 4, fill=1, stroke=0)


def draw_footer(c, firm):
    c.setFillColor(BLUE)
    c.rect(0, 0, W, 30, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 8)
    c.drawString(40, 11, f"{firm} | Confidential")
    c.drawRightString(W - 40, 11, f"Generated {datetime.now().strftime('%B %d, %Y')}")


def draw_flow_circle(c, cx, cy, r, light, dark, lines):
    """A two-ring bubble with (font, size, dy, text) lines drawn in white."""
    draw_circle(c, cx, cy, r, light, dark, 3)
    draw_circle(c, cx, cy, r - 6, dark)
    c.setFillColor(WHITE)
    for font, size, dy, text in lines:
        c.setFont(font, size)
        c.drawCentredString(cx, cy + dy, text)


def build_sacs_pdf(client, report, firm=DEFAULT_FIRM):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f"SACS - {household_name(client)}")
    f = sacs_figures(report)

    # Page 1: the cashflow diagram.
    draw_header(c, firm, "Simple Automated Cash Flow System (SACS)", client, report)

    # Three circles with wide gaps so the arrow labels never get clipped.
    R = 58
    GAP = 74
    STEP = 2 * R + GAP
    total_w = 3 * (2 * R) + 2 * GAP
    in_x = (W - total_w) / 2 + R
    out_x = in_x + STEP
    pr_x = in_x + 2 * STEP
    center_y = H / 2 + 30

    # Arrows first so the circles paint over the shaft ends.
    arr1_x1, arr1_x2 = in_x + R + 6, out_x - R - 6
    mid1 = (arr1_x1 + arr1_x2) / 2
    draw_arrow(c, arr1_x1, center_y, arr1_x2, center_y, RED, 2.5)
    c.setStrokeColor(RED)
    c.setLineWidth(2.5)
    xr = 8
    c.line(mid1 - xr, center_y - xr, mid1 + xr, center_y + xr)
    c.line(mid1 - xr, center_y + xr, mid1 + xr, center_y - xr)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(mid1, center_y + 13, "Transfer")

    arr2_x1, arr2_x2 = out_x + R + 6, pr_x - R - 6
    mid2 = (arr2_x1 + arr2_x2) / 2
    draw_arrow(c, arr2_x1, center_y, arr2_x2, center_y, LIGHT_BLUE, 2.5)
    c.setFillColor(LIGHT_BLUE)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(mid2, center_y + 13, "Excess:")
    c.drawCentredString(mid2, center_y + 3, f"{fmt_money(f['excess'])}/mo")

    draw_flow_circle(
        c,
        in_x,
        center_y,
        R,
        LIGHT_GREEN,
        GREEN,
        [
            ("Helvetica-Bold", 11, 20, "INFLOW"),
            ("Helvetica", 8, 8, "Monthly Take-Home"),
            ("Helvetica-Bold", 14, -8, fmt_money(f["inflow"])),
            ("Helvetica", 8, -22, "per month"),
        ],
    )
    draw_flow_circle(
        c,
        out_x,
        center_y,
        R,
        LIGHT_RED,
        RED,
        [
            ("Helvetica-Bold", 11, 20, "OUTFLOW"),
            ("Helvetica", 8, 8, "Monthly Expenses"),
            ("Helvetica-Bold", 14, -8, fmt_money(f["outflow"])),
            ("Helvetica", 8, -22, "per month"),
        ],
    )
    draw_flow_circle(
        c,
        pr_x,
        center_y,
        R,
        LIGHT_BLUE,
        BLUE,
        [
            ("Helvetica-Bold", 11, 22, "PRIVATE"),
            ("Helvetica-Bold", 11, 10, "RESERVE"),
            ("Helvetica", 8, -4, "Balance"),
            ("Helvetica-Bold", 14, -18, fmt_money(f["pr_balance"])),
        ],
    )
    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica", 9)
    c.drawCentredString(pr_x, center_y - R - 16, f"Target: {fmt_money(f['pr_target'])}")

    box_y, box_h = 100, 70
    for i, (label, val, clr) in enumerate(
        [
            ("Monthly Inflow", f["inflow"], GREEN),
            ("Monthly Outflow", f["outflow"], RED),
            ("Monthly Excess", f["excess"], LIGHT_BLUE),
            ("Reserve Target", f["pr_target"], BLUE),
        ]
    ):
        bx = 40 + i * (W - 80) / 4 + 5
        bw = (W - 80) / 4 - 10
        c.setFillColor(clr)
        c.roundRect(bx, box_y, bw, box_h, 6, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 8)
        c.drawCentredString(bx + bw / 2, box_y + box_h - 18, label)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(bx + bw / 2, box_y + 22, fmt_money(val))

    draw_footer(c, firm)
    c.showPage()

    # Page 2: account detail.
    draw_header(c, firm, "Cash Flow — Account Detail", client, report)
    cards = [
        ("Private Reserve Account", "High-Yield Savings", f["pr_balance"], BLUE),
        (
            "Investment Account (Schwab)",
            f"Cash: {fmt_money(f['schwab_cash'])}",
            f["schwab_balance"],
            LIGHT_BLUE,
        ),
        ("Pinnacle Checking", "Primary Operating Account", f["pinnacle_checking"], GREEN),
        ("Pinnacle Savings", "Secondary Savings", f["pinnacle_savings"], LIGHT_GREEN),
    ]
    y = H - 140
    for label, sub, val, clr in cards:
        c.setFillColor(clr)
        c.roundRect(40, y - 60, W - 80, 55, 8, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(60, y - 20, label)
        c.setFont("Helvetica", 9)
        c.drawString(60, y - 36, sub)
        c.setFont("Helvetica-Bold", 20)
        c.drawRightString(W - 60, y - 28, fmt_money(val))
        y -= 80

    c.setFillColor(GRAY)
    c.roundRect(40, y - 50, W - 80, 45, 8, fill=1, stroke=0)
    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y - 22, "Total Liquid Assets")
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(W - 60, y - 22, fmt_money(f["total_liquid"]))
    c.setFont("Helvetica", 8)
    c.drawString(60, y - 36, "Excluding investment accounts")

    draw_footer(c, firm)
    c.save()
    buf.seek(0)
    return buf


TCC_TITLE = "Total Client Chart (TCC) — Net Worth Overview"
ROW = 48
BOTTOM = 44  # keep content clear of the 30pt footer band


def _pairs(items):
    return [items[i : i + 2] for i in range(0, len(items), 2)]


def _rate_label(rate):
    number = to_number(rate) if rate not in (None, "") else None
    return f"Rate: {number:g}%" if number is not None else "Rate: N/A"


def build_tcc_pdf(client, report, firm=DEFAULT_FIRM):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f"TCC - {household_name(client)}")
    totals = tcc_totals(client, report)
    col_w = (W - 80) / 2 - 10
    right_x = 40 + col_w + 20
    has_spouse = bool(client.get("name_2"))

    draw_header(c, firm, TCC_TITLE, client, report)
    y = H - 120

    def need(height):
        """Start a continuation page when the next block would run into the footer."""
        nonlocal y
        if y - height < BOTTOM:
            draw_footer(c, firm)
            c.showPage()
            draw_header(c, firm, f"{TCC_TITLE} (continued)", client, report)
            y = H - 110

    def section_title(title, color=BLUE):
        nonlocal y
        need(20 + ROW)
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, title)
        c.setFillColor(GOLD)
        c.rect(40, y - 4, W - 80, 2, fill=1, stroke=0)
        y -= 20

    def account_bubble(x, acct, default_type, color, detail=None, cash=None):
        c.setFillColor(color)
        c.roundRect(x, y - 38, col_w, 35, 6, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 8, y - 15, acct.get("type") or default_type)
        c.setFont("Helvetica", 7.5)
        if detail is None:
            detail = f"acct ...{acct['acct_num']}" if acct.get("acct_num") else ""
        c.drawString(x + 8, y - 27, detail)
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(x + col_w - 8, y - 20, fmt_money(acct.get("balance", 0)))
        if cash not in (None, ""):
            c.setFont("Helvetica", 7)
            c.drawRightString(x + col_w - 8, y - 32, f"cash: {fmt_money(cash)}")

    def total_bar(x, width, label, value, fill=GRAY, ink=DARK_GRAY):
        c.setFillColor(fill)
        c.roundRect(x, y - 32, width, 28, 6, fill=1, stroke=0)
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 12, y - 14, label)
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(x + width - 8, y - 14, fmt_money(value))

    for i, suffix in enumerate(("1", "2")):
        name = client.get(f"name_{suffix}", "")
        if not name:
            continue
        bx = 40 + i * (W / 2 - 50)
        c.setFillColor(LIGHT_GREEN)
        c.roundRect(bx, y - 45, W / 2 - 60, 42, 8, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(bx + 12, y - 18, name)
        c.setFont("Helvetica", 8)
        dob = client.get(f"dob_{suffix}") or "N/A"
        age = client.get(f"age_{suffix}") or "N/A"
        ssn = client.get(f"ssn_{suffix}") or "0000"
        c.drawString(bx + 12, y - 34, f"DOB: {dob}  |  Age: {age}  |  SSN: xxx-xx-{ssn}")
    y -= 70

    # Retirement: one column per spouse, drawn row by row so a page break keeps them aligned.
    section_title("RETIREMENT ACCOUNTS")
    left = report.get("retirement_1") or []
    right = (report.get("retirement_2") or []) if has_spouse else []
    for row in range(max(len(left), len(right))):
        need(ROW)
        if row < len(left):
            account_bubble(40, left[row], "IRA", BLUE)
        if row < len(right):
            account_bubble(right_x, right[row], "IRA", LIGHT_BLUE)
        y -= ROW
    y -= 10
    need(40)
    total_bar(40, col_w, f"{client.get('name_1', 'Client 1')} Retirement Total", totals["ret1"])
    if has_spouse:
        total_bar(right_x, col_w, f"{client['name_2']} Retirement Total", totals["ret2"])
    y -= 55

    section_title("NON-RETIREMENT ACCOUNTS")
    for pair in _pairs(report.get("non_retirement") or []):
        need(ROW)
        for x, acct in zip((40, right_x), pair, strict=False):
            account_bubble(x, acct, "Brokerage", LIGHT_BLUE, cash=acct.get("cash"))
        y -= ROW
    y -= 2
    need(40)
    total_bar(40, W - 80, "Non-Retirement Total", totals["nonret"])
    y -= 55

    section_title("TRUST")
    c.setFillColor(DARK_GRAY)
    c.roundRect(40, y - 38, W - 80, 35, 6, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(52, y - 16, f"Primary Residence — {report.get('trust_address') or 'Property'}")
    c.setFont("Helvetica", 8)
    c.drawString(52, y - 28, "Zillow Zestimate")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - 48, y - 22, fmt_money(totals["trust"]))
    y -= 60

    need(45)
    c.setFillColor(BLUE)
    c.roundRect(40, y - 38, W - 80, 35, 8, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(52, y - 16, "Grand Total Net Worth")
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(W - 48, y - 20, fmt_money(totals["grand"]))
    y -= 65

    section_title("LIABILITIES", RED)
    for pair in _pairs(report.get("liabilities") or []):
        need(ROW)
        for x, liab in zip((40, right_x), pair, strict=False):
            account_bubble(x, liab, "Mortgage", LIGHT_RED, detail=_rate_label(liab.get("rate")))
        y -= ROW
    y -= 2
    need(40)
    total_bar(
        40,
        W - 80,
        "Total Liabilities (not subtracted from net worth)",
        totals["liab"],
        fill=HexColor("#FFEBEE"),
        ink=RED,
    )

    draw_footer(c, firm)
    c.save()
    buf.seek(0)
    return buf
