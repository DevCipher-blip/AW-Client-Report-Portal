"""ReportLab drawing for the SACS and TCC client reports."""

import io
import math
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .finance import fmt_money, household_name, sacs_figures, tcc_totals, to_number

FIRM_NAME = "Windbrook Solutions"

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


def draw_header(c, subtitle, client, report):
    c.setFillColor(BLUE)
    c.rect(0, H - 80, W, 80, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, H - 38, FIRM_NAME)
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


def draw_footer(c):
    c.setFillColor(BLUE)
    c.rect(0, 0, W, 30, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 8)
    c.drawString(40, 11, f"{FIRM_NAME} | Confidential")
    c.drawRightString(W - 40, 11, f"Generated {datetime.now().strftime('%B %d, %Y')}")


def draw_flow_circle(c, cx, cy, r, light, dark, lines):
    """A two-ring bubble with (font, size, dy, text) lines drawn in white."""
    draw_circle(c, cx, cy, r, light, dark, 3)
    draw_circle(c, cx, cy, r - 6, dark)
    c.setFillColor(WHITE)
    for font, size, dy, text in lines:
        c.setFont(font, size)
        c.drawCentredString(cx, cy + dy, text)


def build_sacs_pdf(client, report):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f"SACS - {household_name(client)}")
    f = sacs_figures(report)

    # Page 1: the cashflow diagram.
    draw_header(c, "Simple Automated Cash Flow System (SACS)", client, report)

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

    draw_footer(c)
    c.showPage()

    # Page 2: account detail.
    draw_header(c, "Cash Flow — Account Detail", client, report)
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

    draw_footer(c)
    c.save()
    buf.seek(0)
    return buf


def build_tcc_pdf(client, report):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f"TCC - {household_name(client)}")
    totals = tcc_totals(client, report)
    col_w = (W - 80) / 2 - 10

    draw_header(c, "Total Client Chart (TCC) — Net Worth Overview", client, report)

    bubble_y = H - 120
    for i, suffix in enumerate(("1", "2")):
        name = client.get(f"name_{suffix}", "")
        if not name:
            continue
        bx = 40 + i * (W / 2 - 50)
        c.setFillColor(LIGHT_GREEN)
        c.roundRect(bx, bubble_y - 45, W / 2 - 60, 42, 8, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(bx + 12, bubble_y - 18, name)
        c.setFont("Helvetica", 8)
        dob = client.get(f"dob_{suffix}") or "N/A"
        age = client.get(f"age_{suffix}") or "N/A"
        ssn = client.get(f"ssn_{suffix}") or "0000"
        c.drawString(bx + 12, bubble_y - 34, f"DOB: {dob}  |  Age: {age}  |  SSN: xxx-xx-{ssn}")

    def section_title(y, title, color=BLUE):
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, title)
        c.setFillColor(GOLD)
        c.rect(40, y - 4, W - 80, 2, fill=1, stroke=0)

    def account_bubble(x, y, acct_type, acct_num, balance, cash=None, color=BLUE):
        c.setFillColor(color)
        c.roundRect(x, y - 38, col_w, 35, 6, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 8, y - 15, acct_type)
        c.setFont("Helvetica", 7.5)
        c.drawString(x + 8, y - 27, f"acct ...{acct_num}" if acct_num else "")
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(x + col_w - 8, y - 20, fmt_money(balance))
        if cash is not None:
            c.setFont("Helvetica", 7)
            c.drawRightString(x + col_w - 8, y - 32, f"cash: {fmt_money(cash)}")

    def total_bar(x, y, width, label, value, fill=GRAY, ink=DARK_GRAY):
        c.setFillColor(fill)
        c.roundRect(x, y - 32, width, 28, 6, fill=1, stroke=0)
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 12, y - 14, label)
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(x + width - 8, y - 14, fmt_money(value))

    ret_y = bubble_y - 70
    section_title(ret_y, "RETIREMENT ACCOUNTS")
    ret_y -= 20

    ay = ret_y
    for acct in report.get("retirement_1", []):
        account_bubble(40, ay, acct.get("type", "IRA"), acct.get("acct_num", ""), acct.get("balance", 0))
        ay -= 48
    min_y = ay
    if client.get("name_2"):
        ay2 = ret_y
        for acct in report.get("retirement_2", []):
            account_bubble(
                40 + col_w + 20,
                ay2,
                acct.get("type", "IRA"),
                acct.get("acct_num", ""),
                acct.get("balance", 0),
                color=LIGHT_BLUE,
            )
            ay2 -= 48
        min_y = min(ay, ay2)

    min_y -= 10
    total_bar(40, min_y, col_w, f"{client.get('name_1', 'Client 1')} Retirement Total", totals["ret1"])
    if client.get("name_2"):
        total_bar(40 + col_w + 20, min_y, col_w, f"{client['name_2']} Retirement Total", totals["ret2"])

    nr_y = min_y - 55
    section_title(nr_y, "NON-RETIREMENT ACCOUNTS")
    nr_y -= 20
    nr_x = 40
    for acct in report.get("non_retirement", []):
        account_bubble(
            nr_x,
            nr_y,
            acct.get("type", "Brokerage"),
            acct.get("acct_num", ""),
            acct.get("balance", 0),
            acct.get("cash"),
            color=LIGHT_BLUE,
        )
        nr_x += col_w + 20
        if nr_x + col_w > W - 40:
            nr_x = 40
            nr_y -= 48
    nr_y -= 50
    total_bar(40, nr_y, W - 80, "Non-Retirement Total", totals["nonret"])

    trust_y = nr_y - 55
    section_title(trust_y, "TRUST")
    trust_y -= 20
    c.setFillColor(DARK_GRAY)
    c.roundRect(40, trust_y - 38, W - 80, 35, 6, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(52, trust_y - 16, f"Primary Residence — {report.get('trust_address', 'Property')}")
    c.setFont("Helvetica", 8)
    c.drawString(52, trust_y - 28, "Zillow Zestimate")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - 48, trust_y - 22, fmt_money(totals["trust"]))

    gt_y = trust_y - 60
    c.setFillColor(BLUE)
    c.roundRect(40, gt_y - 38, W - 80, 35, 8, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(52, gt_y - 16, "Grand Total Net Worth")
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(W - 48, gt_y - 20, fmt_money(totals["grand"]))

    liab_y = gt_y - 65
    section_title(liab_y, "LIABILITIES", RED)
    liab_y -= 20
    lx = 40
    for liab in report.get("liabilities", []):
        c.setFillColor(LIGHT_RED)
        c.roundRect(lx, liab_y - 38, col_w, 35, 6, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(lx + 8, liab_y - 15, liab.get("type", "Mortgage"))
        c.setFont("Helvetica", 7.5)
        c.drawString(lx + 8, liab_y - 27, f"Rate: {liab.get('rate', 'N/A')}%")
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(lx + col_w - 8, liab_y - 20, fmt_money(to_number(liab.get("balance", 0))))
        lx += col_w + 20
        if lx + col_w > W - 40:
            lx = 40
            liab_y -= 48
    liab_y -= 50
    if liab_y > 40:
        total_bar(
            40,
            liab_y,
            W - 80,
            "Total Liabilities (not subtracted from net worth)",
            totals["liab"],
            fill=HexColor("#FFEBEE"),
            ink=RED,
        )

    draw_footer(c)
    c.save()
    buf.seek(0)
    return buf
