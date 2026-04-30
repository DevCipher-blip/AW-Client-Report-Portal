import os, json, sqlite3, io
from flask import Flask, request, jsonify, send_file, render_template_string
from datetime import datetime, date
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import math

app = Flask(__name__)
DB_PATH = os.environ.get("RAILWAY_DATABASE_PATH", "portal.db")

# ─── DB SETUP ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        quarter TEXT NOT NULL,
        year INTEGER NOT NULL,
        report_data TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(client_id) REFERENCES clients(id)
    );
    """)
    db.commit()
    db.close()

init_db()

# ─── API ──────────────────────────────────────────────────────────────────────
@app.route("/api/clients", methods=["GET"])
def list_clients():
    db = get_db()
    rows = db.execute("SELECT id, data, updated_at FROM clients ORDER BY id").fetchall()
    db.close()
    result = []
    for r in rows:
        d = json.loads(r["data"])
        d["id"] = r["id"]
        d["updated_at"] = r["updated_at"]
        result.append(d)
    return jsonify(result)

def json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None

@app.route("/api/clients", methods=["POST"])
def create_client():
    data = json_object()
    if data is None:
        return jsonify({"error": "expected a JSON object"}), 400
    db = get_db()
    cur = db.execute("INSERT INTO clients (data) VALUES (?)", [json.dumps(data)])
    db.commit()
    cid = cur.lastrowid
    db.close()
    return jsonify({"id": cid, **data})

@app.route("/api/clients/<int:cid>", methods=["GET"])
def get_client(cid):
    db = get_db()
    row = db.execute("SELECT id, data FROM clients WHERE id=?", [cid]).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    d = json.loads(row["data"])
    d["id"] = row["id"]
    return jsonify(d)

@app.route("/api/clients/<int:cid>", methods=["PUT"])
def update_client(cid):
    data = json_object()
    if data is None:
        return jsonify({"error": "expected a JSON object"}), 400
    db = get_db()
    cur = db.execute("UPDATE clients SET data=?, updated_at=datetime('now') WHERE id=?",
                     [json.dumps(data), cid])
    db.commit()
    db.close()
    if cur.rowcount == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"id": cid, **data})

@app.route("/api/clients/<int:cid>", methods=["DELETE"])
def delete_client(cid):
    db = get_db()
    db.execute("DELETE FROM clients WHERE id=?", [cid])
    db.execute("DELETE FROM reports WHERE client_id=?", [cid])
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/clients/<int:cid>/reports", methods=["GET"])
def list_reports(cid):
    db = get_db()
    rows = db.execute(
        "SELECT id, quarter, year, report_data, created_at FROM reports WHERE client_id=? ORDER BY year DESC, quarter DESC, id DESC",
        [cid]).fetchall()
    db.close()
    result = []
    for r in rows:
        d = json.loads(r["report_data"])
        d["id"] = r["id"]
        d["quarter"] = r["quarter"]
        d["year"] = r["year"]
        d["created_at"] = r["created_at"]
        result.append(d)
    return jsonify(result)

@app.route("/api/clients/<int:cid>/reports", methods=["POST"])
def save_report(cid):
    data = json_object()
    if data is None:
        return jsonify({"error": "expected a JSON object"}), 400
    quarter = data.get("quarter", "Q1")
    year = data.get("year", datetime.now().year)
    db = get_db()
    if not db.execute("SELECT 1 FROM clients WHERE id=?", [cid]).fetchone():
        db.close()
        return jsonify({"error": "not found"}), 404
    cur = db.execute(
        "INSERT INTO reports (client_id, quarter, year, report_data) VALUES (?,?,?,?)",
        [cid, quarter, year, json.dumps(data)])
    db.commit()
    rid = cur.lastrowid
    db.close()
    return jsonify({"id": rid})

@app.route("/api/reports/<int:rid>/sacs.pdf")
def download_sacs(rid):
    db = get_db()
    row = db.execute("SELECT r.report_data, c.data FROM reports r JOIN clients c ON r.client_id=c.id WHERE r.id=?", [rid]).fetchone()
    db.close()
    if not row:
        return "Not found", 404
    report = json.loads(row["report_data"])
    client = json.loads(row["data"])
    buf = generate_sacs_pdf(client, report)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"SACS_{client.get('name_1','Client')}_{report.get('quarter','')}{report.get('year','')}.pdf")

@app.route("/api/reports/<int:rid>/tcc.pdf")
def download_tcc(rid):
    db = get_db()
    row = db.execute("SELECT r.report_data, c.data FROM reports r JOIN clients c ON r.client_id=c.id WHERE r.id=?", [rid]).fetchone()
    db.close()
    if not row:
        return "Not found", 404
    report = json.loads(row["report_data"])
    client = json.loads(row["data"])
    buf = generate_tcc_pdf(client, report)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"TCC_{client.get('name_1','Client')}_{report.get('quarter','')}{report.get('year','')}.pdf")

# ─── PDF GENERATION ──────────────────────────────────────────────────────────
BLUE = HexColor("#1B3A6B")
LIGHT_BLUE = HexColor("#2E5FAC")
GREEN = HexColor("#2E7D32")
LIGHT_GREEN = HexColor("#4CAF50")
RED = HexColor("#C62828")
LIGHT_RED = HexColor("#EF5350")
GRAY = HexColor("#F5F5F5")
DARK_GRAY = HexColor("#424242")
SILVER = HexColor("#9E9E9E")
WHITE = colors.white
BLACK = colors.black
GOLD = HexColor("#C8A951")

def to_number(val):
    """Form fields arrive as strings and are often left blank; treat those as 0."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

def fmt_money(val):
    return f"${to_number(val):,.0f}"

def draw_circle(c, cx, cy, r, fill_color, stroke_color=None, stroke_width=2):
    c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(stroke_width)
        c.circle(cx, cy, r, fill=1, stroke=1)
    else:
        c.circle(cx, cy, r, fill=1, stroke=0)

def draw_text_centered(c, text, cx, cy, font="Helvetica-Bold", size=10, color=WHITE):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawCentredString(cx, cy, text)

def draw_arrow(c, x1, y1, x2, y2, color, width=2):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)
    # arrowhead
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_len = 10
    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - arrow_len * math.cos(angle - 0.4), y2 - arrow_len * math.sin(angle - 0.4))
    p.lineTo(x2 - arrow_len * math.cos(angle + 0.4), y2 - arrow_len * math.sin(angle + 0.4))
    p.close()
    c.drawPath(p, fill=1, stroke=0)

def generate_sacs_pdf(client, report):
    buf = io.BytesIO()
    W, H = letter
    c = canvas.Canvas(buf, pagesize=letter)

    # ── PAGE 1: SACS Cashflow Diagram ──
    # Header bar
    c.setFillColor(BLUE)
    c.rect(0, H - 80, W, 80, fill=1, stroke=0)

    # Company name
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, H - 38, "Windbrook Solutions")
    c.setFont("Helvetica", 11)
    c.drawString(40, H - 56, "Simple Automated Cash Flow System (SACS)")

    # Client name + date top right
    name = f"{client.get('name_1', '')} & {client.get('name_2', '')}" if client.get('name_2') else client.get('name_1', 'Client')
    qtr = f"{report.get('quarter', 'Q1')} {report.get('year', datetime.now().year)}"
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(W - 40, H - 38, name)
    c.setFont("Helvetica", 10)
    c.drawRightString(W - 40, H - 56, qtr)

    # Gold accent line
    c.setFillColor(GOLD)
    c.rect(0, H - 84, W, 4, fill=1, stroke=0)

    # Calculations
    inflow = to_number(report.get("inflow", 0))
    outflow = to_number(report.get("outflow", 0))
    excess = inflow - outflow
    pr_balance = to_number(report.get("private_reserve_balance", 0))
    pr_target = to_number(report.get("private_reserve_target", 0))

    # Layout: three circles with generous gaps so labels never get clipped.
    # Page W=612. We use margins of 50 each side → usable = 512.
    # Formula: 3*(2R) + 2*GAP = usable  →  R=58, GAP=70: 3*116+140=488 ✓ (24px spare)
    R   = 58    # circle radius — noticeably smaller than before
    GAP = 74    # wide gap so arrow labels have breathing room
    STEP = 2 * R + GAP          # = 190

    # Centre the three circles horizontally on the page
    total_w = 3 * (2 * R) + 2 * GAP   # = 496
    start_x = (W - total_w) / 2 + R   # left circle centre
    in_x  = start_x
    out_x = start_x + STEP
    pr_x  = start_x + 2 * STEP

    center_y = H / 2 + 30

    # ── Draw arrows FIRST so circles paint over the shaft ends cleanly ──

    # Arrow 1 (red): inflow → outflow
    arr1_x1 = in_x + R + 6
    arr1_x2 = out_x - R - 6
    mid1 = (arr1_x1 + arr1_x2) / 2
    draw_arrow(c, arr1_x1, center_y, arr1_x2, center_y, RED, 2.5)

    # Red X centred in the gap
    c.setStrokeColor(RED)
    c.setLineWidth(2.5)
    xr = 8
    c.line(mid1 - xr, center_y - xr, mid1 + xr, center_y + xr)
    c.line(mid1 - xr, center_y + xr, mid1 + xr, center_y - xr)

    # "Transfer" label above the gap
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(mid1, center_y + 13, "Transfer")

    # Arrow 2 (blue): outflow → private reserve
    arr2_x1 = out_x + R + 6
    arr2_x2 = pr_x - R - 6
    mid2 = (arr2_x1 + arr2_x2) / 2
    draw_arrow(c, arr2_x1, center_y, arr2_x2, center_y, LIGHT_BLUE, 2.5)

    # "Excess" label above the gap — split onto two lines so it never overflows
    exc_line1 = "Excess:"
    exc_line2 = f"{fmt_money(excess)}/mo"
    c.setFillColor(LIGHT_BLUE)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(mid2, center_y + 13, exc_line1)
    c.drawCentredString(mid2, center_y + 3,  exc_line2)

    # ── Circles on top ──

    # INFLOW (green)
    draw_circle(c, in_x, center_y, R,     LIGHT_GREEN, GREEN, 3)
    draw_circle(c, in_x, center_y, R - 6, GREEN, None)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(in_x, center_y + 20, "INFLOW")
    c.setFont("Helvetica", 8)
    c.drawCentredString(in_x, center_y + 8,  "Monthly Take-Home")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(in_x, center_y - 8,  fmt_money(inflow))
    c.setFont("Helvetica", 8)
    c.drawCentredString(in_x, center_y - 22, "per month")

    # OUTFLOW (red)
    draw_circle(c, out_x, center_y, R,     LIGHT_RED, RED, 3)
    draw_circle(c, out_x, center_y, R - 6, RED, None)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(out_x, center_y + 20, "OUTFLOW")
    c.setFont("Helvetica", 8)
    c.drawCentredString(out_x, center_y + 8,  "Monthly Expenses")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(out_x, center_y - 8,  fmt_money(outflow))
    c.setFont("Helvetica", 8)
    c.drawCentredString(out_x, center_y - 22, "per month")

    # PRIVATE RESERVE (blue)
    draw_circle(c, pr_x, center_y, R,     LIGHT_BLUE, BLUE, 3)
    draw_circle(c, pr_x, center_y, R - 6, BLUE, None)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(pr_x, center_y + 22, "PRIVATE")
    c.drawCentredString(pr_x, center_y + 10, "RESERVE")
    c.setFont("Helvetica", 8)
    c.drawCentredString(pr_x, center_y - 4,  "Balance")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(pr_x, center_y - 18, fmt_money(pr_balance))

    # Target label below the blue circle
    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica", 9)
    c.drawCentredString(pr_x, center_y - R - 16, f"Target: {fmt_money(pr_target)}")

    # Bottom info boxes
    box_y = 100
    box_h = 70
    for i, (label, val, clr) in enumerate([
        ("Monthly Inflow", fmt_money(inflow), GREEN),
        ("Monthly Outflow", fmt_money(outflow), RED),
        ("Monthly Excess", fmt_money(excess), LIGHT_BLUE),
        ("Reserve Target", fmt_money(pr_target), BLUE),
    ]):
        bx = 40 + i * (W - 80) / 4 + 5
        bw = (W - 80) / 4 - 10
        c.setFillColor(clr)
        c.roundRect(bx, box_y, bw, box_h, 6, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 8)
        c.drawCentredString(bx + bw/2, box_y + box_h - 18, label)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(bx + bw/2, box_y + 22, val)

    # Footer
    c.setFillColor(BLUE)
    c.rect(0, 0, W, 30, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 8)
    c.drawString(40, 11, "Windbrook Solutions | Confidential")
    c.drawRightString(W - 40, 11, f"Generated {datetime.now().strftime('%B %d, %Y')}")

    c.showPage()

    # ── PAGE 2: Private Reserve Detail ──
    c.setFillColor(BLUE)
    c.rect(0, H - 80, W, 80, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, H - 38, "Windbrook Solutions")
    c.setFont("Helvetica", 11)
    c.drawString(40, H - 56, "Cash Flow — Account Detail")
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(W - 40, H - 38, name)
    c.setFont("Helvetica", 10)
    c.drawRightString(W - 40, H - 56, qtr)
    c.setFillColor(GOLD)
    c.rect(0, H - 84, W, 4, fill=1, stroke=0)

    # Account detail cards
    schwab_balance = to_number(report.get("schwab_balance", 0))
    schwab_cash = to_number(report.get("schwab_cash", 0))
    pinnacle_checking = to_number(report.get("pinnacle_checking", 0))
    pinnacle_savings = to_number(report.get("pinnacle_savings", 0))

    cards = [
        ("Private Reserve Account", "High-Yield Savings", pr_balance, BLUE),
        ("Investment Account (Schwab)", f"Cash: {fmt_money(schwab_cash)}", schwab_balance, LIGHT_BLUE),
        ("Pinnacle Checking", "Primary Operating Account", pinnacle_checking, GREEN),
        ("Pinnacle Savings", "Secondary Savings", pinnacle_savings, LIGHT_GREEN),
    ]

    cy2 = H - 140
    for label, sub, val, clr in cards:
        c.setFillColor(clr)
        c.roundRect(40, cy2 - 60, W - 80, 55, 8, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(60, cy2 - 20, label)
        c.setFont("Helvetica", 9)
        c.drawString(60, cy2 - 36, sub)
        c.setFont("Helvetica-Bold", 20)
        c.drawRightString(W - 60, cy2 - 28, fmt_money(val))
        cy2 -= 80

    # Summary
    total_liquid = pr_balance + pinnacle_checking + pinnacle_savings
    c.setFillColor(GRAY)
    c.roundRect(40, cy2 - 50, W - 80, 45, 8, fill=1, stroke=0)
    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, cy2 - 22, "Total Liquid Assets")
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(W - 60, cy2 - 22, fmt_money(total_liquid))
    c.setFont("Helvetica", 8)
    c.drawString(60, cy2 - 36, "Excluding investment accounts")

    # Footer
    c.setFillColor(BLUE)
    c.rect(0, 0, W, 30, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 8)
    c.drawString(40, 11, "Windbrook Solutions | Confidential")
    c.drawRightString(W - 40, 11, f"Generated {datetime.now().strftime('%B %d, %Y')}")

    c.save()
    buf.seek(0)
    return buf


def generate_tcc_pdf(client, report):
    buf = io.BytesIO()
    W, H = letter
    c = canvas.Canvas(buf, pagesize=letter)

    name = f"{client.get('name_1', '')} & {client.get('name_2', '')}" if client.get('name_2') else client.get('name_1', 'Client')
    qtr = f"{report.get('quarter', 'Q1')} {report.get('year', datetime.now().year)}"

    # Header
    c.setFillColor(BLUE)
    c.rect(0, H - 80, W, 80, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, H - 38, "Windbrook Solutions")
    c.setFont("Helvetica", 11)
    c.drawString(40, H - 56, "Total Client Chart (TCC) — Net Worth Overview")
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(W - 40, H - 38, name)
    c.setFont("Helvetica", 10)
    c.drawRightString(W - 40, H - 56, qtr)
    c.setFillColor(GOLD)
    c.rect(0, H - 84, W, 4, fill=1, stroke=0)

    # Client info bubbles
    bubble_y = H - 120
    for i, (n_key, dob_key, age_key, ssn_key) in enumerate([
        ("name_1", "dob_1", "age_1", "ssn_1"),
        ("name_2", "dob_2", "age_2", "ssn_2"),
    ]):
        n = client.get(n_key, "")
        if not n:
            continue
        bx = 40 + i * (W / 2 - 50)
        c.setFillColor(LIGHT_GREEN)
        c.roundRect(bx, bubble_y - 45, W / 2 - 60, 42, 8, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(bx + 12, bubble_y - 18, n)
        c.setFont("Helvetica", 8)
        info = f"DOB: {client.get(dob_key, 'N/A')}  |  Age: {client.get(age_key, 'N/A')}  |  SSN: xxx-xx-{client.get(ssn_key, '0000')}"
        c.drawString(bx + 12, bubble_y - 34, info)

    # ── RETIREMENT SECTION ──
    ret_y = bubble_y - 70
    c.setFillColor(BLUE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, ret_y, "RETIREMENT ACCOUNTS")
    c.setFillColor(GOLD)
    c.rect(40, ret_y - 4, W - 80, 2, fill=1, stroke=0)
    ret_y -= 20

    col_w = (W - 80) / 2 - 10
    totals = {"ret1": 0, "ret2": 0, "nonret": 0, "trust": 0, "liab": 0}

    def account_bubble(cx, cy, acct_type, acct_num, balance, cash=None, color=BLUE):
        nonlocal totals
        c.setFillColor(color)
        c.roundRect(cx, cy - 38, col_w, 35, 6, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(cx + 8, cy - 15, acct_type)
        c.setFont("Helvetica", 7.5)
        c.drawString(cx + 8, cy - 27, f"acct ...{acct_num}" if acct_num else "")
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(cx + col_w - 8, cy - 20, fmt_money(balance))
        if cash is not None:
            c.setFont("Helvetica", 7)
            c.drawRightString(cx + col_w - 8, cy - 32, f"cash: {fmt_money(cash)}")
        return to_number(balance)

    # Client 1 retirement
    ret_accounts_1 = report.get("retirement_1", [])
    ay = ret_y
    for acct in ret_accounts_1:
        v = account_bubble(40, ay, acct.get("type", "IRA"), acct.get("acct_num", ""), acct.get("balance", 0), color=BLUE)
        totals["ret1"] += v
        ay -= 48

    # Client 2 retirement
    if client.get("name_2"):
        ret_accounts_2 = report.get("retirement_2", [])
        ay2 = ret_y
        for acct in ret_accounts_2:
            v = account_bubble(40 + col_w + 20, ay2, acct.get("type", "IRA"), acct.get("acct_num", ""), acct.get("balance", 0), color=LIGHT_BLUE)
            totals["ret2"] += v
            ay2 -= 48
        min_y = min(ay, ay2)
    else:
        min_y = ay

    # Retirement totals
    min_y -= 10
    c.setFillColor(GRAY)
    c.roundRect(40, min_y - 32, col_w, 28, 6, fill=1, stroke=0)
    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(52, min_y - 14, f"{client.get('name_1','Client 1')} Retirement Total")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(40 + col_w - 8, min_y - 14, fmt_money(totals["ret1"]))

    if client.get("name_2"):
        c.setFillColor(GRAY)
        c.roundRect(40 + col_w + 20, min_y - 32, col_w, 28, 6, fill=1, stroke=0)
        c.setFillColor(DARK_GRAY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(52 + col_w + 20, min_y - 14, f"{client.get('name_2','Client 2')} Retirement Total")
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(40 + 2 * col_w + 20 - 8, min_y - 14, fmt_money(totals["ret2"]))

    # ── NON-RETIREMENT SECTION ──
    nr_y = min_y - 55
    c.setFillColor(BLUE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, nr_y, "NON-RETIREMENT ACCOUNTS")
    c.setFillColor(GOLD)
    c.rect(40, nr_y - 4, W - 80, 2, fill=1, stroke=0)
    nr_y -= 20

    nr_accounts = report.get("non_retirement", [])
    nr_ax = 40
    for acct in nr_accounts:
        v = account_bubble(nr_ax, nr_y, acct.get("type", "Brokerage"), acct.get("acct_num", ""), acct.get("balance", 0), acct.get("cash"), color=LIGHT_BLUE)
        totals["nonret"] += v
        nr_ax += col_w + 20
        if nr_ax + col_w > W - 40:
            nr_ax = 40
            nr_y -= 48

    nr_y -= 50
    c.setFillColor(GRAY)
    c.roundRect(40, nr_y - 32, W - 80, 28, 6, fill=1, stroke=0)
    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(52, nr_y - 14, "Non-Retirement Total")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(W - 48, nr_y - 14, fmt_money(totals["nonret"]))

    # ── TRUST ──
    trust_y = nr_y - 55
    trust_val = to_number(report.get("trust_value", 0))
    trust_addr = report.get("trust_address", "Property")
    totals["trust"] = trust_val

    c.setFillColor(BLUE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, trust_y, "TRUST")
    c.setFillColor(GOLD)
    c.rect(40, trust_y - 4, W - 80, 2, fill=1, stroke=0)
    trust_y -= 20

    c.setFillColor(DARK_GRAY)
    c.roundRect(40, trust_y - 38, W - 80, 35, 6, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(52, trust_y - 16, f"Primary Residence — {trust_addr}")
    c.setFont("Helvetica", 8)
    c.drawString(52, trust_y - 28, "Zillow Zestimate")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - 48, trust_y - 22, fmt_money(trust_val))

    # ── GRAND TOTAL ──
    grand = totals["ret1"] + totals["ret2"] + totals["nonret"] + totals["trust"]
    gt_y = trust_y - 60
    c.setFillColor(BLUE)
    c.roundRect(40, gt_y - 38, W - 80, 35, 8, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(52, gt_y - 16, "Grand Total Net Worth")
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(W - 48, gt_y - 20, fmt_money(grand))

    # ── LIABILITIES ──
    liab_y = gt_y - 65
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, liab_y, "LIABILITIES")
    c.setFillColor(GOLD)
    c.rect(40, liab_y - 4, W - 80, 2, fill=1, stroke=0)
    liab_y -= 20

    liabilities = report.get("liabilities", [])
    lx = 40
    for liab in liabilities:
        v = to_number(liab.get("balance", 0))
        totals["liab"] += v
        c.setFillColor(LIGHT_RED)
        c.roundRect(lx, liab_y - 38, col_w, 35, 6, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(lx + 8, liab_y - 15, liab.get("type", "Mortgage"))
        c.setFont("Helvetica", 7.5)
        c.drawString(lx + 8, liab_y - 27, f"Rate: {liab.get('rate', 'N/A')}%")
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(lx + col_w - 8, liab_y - 20, fmt_money(v))
        lx += col_w + 20
        if lx + col_w > W - 40:
            lx = 40
            liab_y -= 48

    liab_y -= 50
    if liab_y > 40:
        c.setFillColor(HexColor("#FFEBEE"))
        c.roundRect(40, liab_y - 32, W - 80, 28, 6, fill=1, stroke=0)
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(52, liab_y - 14, "Total Liabilities (not subtracted from net worth)")
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(W - 48, liab_y - 14, fmt_money(totals["liab"]))

    # Footer
    c.setFillColor(BLUE)
    c.rect(0, 0, W, 30, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 8)
    c.drawString(40, 11, "Windbrook Solutions | Confidential")
    c.drawRightString(W - 40, 11, f"Generated {datetime.now().strftime('%B %d, %Y')}")

    c.save()
    buf.seek(0)
    return buf


# ─── FRONTEND ─────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AW Client Report Portal</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>
:root {
  --navy: #1B3A6B;
  --navy-light: #2E5FAC;
  --gold: #C8A951;
  --gold-light: #E8C96A;
  --green: #2E7D32;
  --red: #C62828;
  --bg: #F4F6FA;
  --surface: #FFFFFF;
  --border: #E0E5F0;
  --text: #1A1E2E;
  --muted: #6B7280;
  --sidebar-w: 260px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); display: flex; min-height: 100vh; }

/* Sidebar */
#sidebar {
  width: var(--sidebar-w);
  background: var(--navy);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0; left: 0; bottom: 0;
  z-index: 100;
}
.sidebar-logo {
  padding: 28px 24px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.sidebar-logo h1 {
  font-family: 'DM Serif Display', serif;
  font-size: 18px;
  color: white;
  line-height: 1.2;
}
.sidebar-logo span {
  font-size: 11px;
  color: var(--gold);
  font-weight: 500;
  letter-spacing: 1px;
  text-transform: uppercase;
}
.sidebar-nav {
  padding: 16px 12px;
  flex: 1;
  overflow-y: auto;
}
.nav-section {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.4);
  padding: 12px 12px 6px;
}
.nav-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  border-radius: 8px;
  border: none;
  background: none;
  color: rgba(255,255,255,0.75);
  font-family: 'DM Sans', sans-serif;
  font-size: 13.5px;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s;
}
.nav-btn:hover { background: rgba(255,255,255,0.08); color: white; }
.nav-btn.active { background: rgba(200,169,81,0.2); color: var(--gold); }
.nav-btn .icon { font-size: 16px; width: 20px; text-align: center; }
#client-list-nav { display: none; }
.client-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px 7px 44px;
  border-radius: 6px;
  cursor: pointer;
  color: rgba(255,255,255,0.6);
  font-size: 12.5px;
  transition: all 0.15s;
}
.client-nav-item:hover { color: white; background: rgba(255,255,255,0.06); }
.client-nav-item.active { color: var(--gold-light); }
.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255,255,255,0.08);
  font-size: 11px;
  color: rgba(255,255,255,0.3);
  text-align: center;
}

/* Main */
#main {
  margin-left: var(--sidebar-w);
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
.topbar {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 16px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 50;
}
.topbar-title { font-family: 'DM Serif Display', serif; font-size: 22px; color: var(--navy); }
.topbar-sub { font-size: 13px; color: var(--muted); margin-top: 1px; }
.btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 18px;
  border-radius: 8px;
  font-family: 'DM Sans', sans-serif;
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
}
.btn-primary { background: var(--navy); color: white; }
.btn-primary:hover { background: var(--navy-light); }
.btn-gold { background: var(--gold); color: var(--navy); }
.btn-gold:hover { background: var(--gold-light); }
.btn-outline { background: white; color: var(--navy); border: 1.5px solid var(--border); }
.btn-outline:hover { border-color: var(--navy); }
.btn-danger { background: #FEE2E2; color: var(--red); border: none; }
.btn-danger:hover { background: #FECACA; }
.btn-sm { padding: 6px 12px; font-size: 12px; }
.btn-green { background: #DCFCE7; color: var(--green); }
.btn-green:hover { background: #BBF7D0; }

#content { padding: 32px; flex: 1; }

/* Cards */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.card-header {
  padding: 18px 24px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-title { font-family: 'DM Serif Display', serif; font-size: 16px; color: var(--navy); }
.card-body { padding: 24px; }

/* Client grid */
.client-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 24px;
}
.client-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}
.client-card:hover { border-color: var(--navy-light); box-shadow: 0 4px 20px rgba(27,58,107,0.1); transform: translateY(-2px); }
.client-card-initials {
  width: 48px; height: 48px;
  border-radius: 50%;
  background: var(--navy);
  display: flex; align-items: center; justify-content: center;
  color: var(--gold);
  font-family: 'DM Serif Display', serif;
  font-size: 17px;
  margin-bottom: 14px;
}
.client-card-name { font-weight: 600; font-size: 15px; color: var(--navy); }
.client-card-sub { font-size: 12px; color: var(--muted); margin-top: 3px; }
.client-card-meta { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.tag {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 20px;
  font-weight: 500;
}
.tag-blue { background: #EEF2FF; color: var(--navy-light); }
.tag-gold { background: #FEF9EC; color: #92600A; }

/* Forms */
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group.full { grid-column: 1 / -1; }
label { font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
input, select, textarea {
  padding: 10px 12px;
  border: 1.5px solid var(--border);
  border-radius: 8px;
  font-family: 'DM Sans', sans-serif;
  font-size: 13.5px;
  color: var(--text);
  background: white;
  outline: none;
  transition: border-color 0.15s;
}
input:focus, select:focus { border-color: var(--navy-light); }
input.error { border-color: var(--red); }

.section-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 24px 0 16px;
}
.section-divider span {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--navy);
  white-space: nowrap;
}
.section-divider::before, .section-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

/* Account rows */
.account-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 10px;
  background: var(--bg);
  border-radius: 8px;
  margin-bottom: 8px;
}
.account-row .form-group { flex: 1; margin: 0; }
.btn-icon {
  width: 34px; height: 34px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
  background: #FEE2E2;
  color: var(--red);
  transition: all 0.15s;
}
.btn-icon:hover { background: #FECACA; }
.btn-add {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--navy-light);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  background: none;
  padding: 4px 0;
  margin-top: 4px;
  font-family: 'DM Sans', sans-serif;
}
.btn-add:hover { color: var(--navy); }

/* Report form */
.report-section {
  background: var(--bg);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 16px;
}
.report-section-title {
  font-family: 'DM Serif Display', serif;
  font-size: 15px;
  color: var(--navy);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.calc-display {
  background: var(--navy);
  color: var(--gold);
  border-radius: 8px;
  padding: 12px 16px;
  font-family: 'DM Serif Display', serif;
  font-size: 18px;
  text-align: center;
  margin-top: 4px;
}
.calc-label { font-size: 11px; color: rgba(255,255,255,0.6); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }

/* Report history */
.report-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
  border-bottom: 1px solid var(--border);
}
.report-row:last-child { border-bottom: none; }

/* Toast */
#toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: var(--navy);
  color: white;
  padding: 12px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  display: none;
  z-index: 999;
  animation: slideIn 0.2s ease;
  max-width: 300px;
}
@keyframes slideIn { from { transform: translateY(10px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10,15,35,0.6);
  backdrop-filter: blur(4px);
  z-index: 200;
  display: none;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.modal-overlay.open { display: flex; }
.modal {
  background: white;
  border-radius: 14px;
  width: 100%;
  max-width: 760px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 24px 80px rgba(0,0,0,0.2);
}
.modal-header {
  padding: 22px 28px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  background: white;
  z-index: 10;
}
.modal-close {
  width: 32px; height: 32px;
  border-radius: 6px;
  border: none;
  background: var(--bg);
  cursor: pointer;
  font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  color: var(--muted);
}
.modal-close:hover { background: var(--border); }
.modal-body { padding: 28px; }
.modal-footer {
  padding: 16px 28px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  position: sticky;
  bottom: 0;
  background: white;
}

/* Stats */
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 28px; }
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px;
}
.stat-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 6px; }
.stat-value { font-family: 'DM Serif Display', serif; font-size: 28px; color: var(--navy); }
.stat-sub { font-size: 11px; color: var(--muted); margin-top: 3px; }

/* Empty state */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}
.empty-state .icon { font-size: 48px; margin-bottom: 16px; }
.empty-state h3 { font-family: 'DM Serif Display', serif; font-size: 20px; color: var(--navy); margin-bottom: 8px; }
.empty-state p { color: var(--muted); font-size: 14px; }

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px; height: 20px;
  border-radius: 50%;
  background: var(--gold);
  color: var(--navy);
  font-size: 11px;
  font-weight: 700;
}

.prev-val {
  font-size: 11px;
  color: var(--muted);
  margin-top: 3px;
}
</style>
</head>
<body>

<div id="sidebar">
  <div class="sidebar-logo">
    <h1>Windbrook<br>Solutions</h1>
    <span>Client Report Portal</span>
  </div>
  <nav class="sidebar-nav">
    <div class="nav-section">Navigation</div>
    <button class="nav-btn active" onclick="showView('dashboard')" id="nav-dashboard">
      <span class="icon">⊞</span> Dashboard
    </button>
    <button class="nav-btn" onclick="showView('clients')" id="nav-clients">
      <span class="icon">◎</span> Clients
    </button>
    <div id="client-list-nav"></div>
    <button class="nav-btn" onclick="openClientModal()" id="nav-add">
      <span class="icon">＋</span> Add Client
    </button>
  </nav>
  <div class="sidebar-footer">AW Client Portal v1.0</div>
</div>

<div id="main">
  <div class="topbar">
    <div>
      <div class="topbar-title" id="topbar-title">Dashboard</div>
      <div class="topbar-sub" id="topbar-sub">Overview of all clients and reports</div>
    </div>
    <div id="topbar-actions"></div>
  </div>
  <div id="content"></div>
</div>

<!-- Client Modal -->
<div class="modal-overlay" id="client-modal">
  <div class="modal">
    <div class="modal-header">
      <span style="font-family:'DM Serif Display',serif;font-size:18px;color:var(--navy)" id="client-modal-title">Add New Client</span>
      <button class="modal-close" onclick="closeClientModal()">✕</button>
    </div>
    <div class="modal-body" id="client-modal-body"></div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeClientModal()">Cancel</button>
      <button class="btn btn-primary" onclick="saveClient()">Save Client</button>
    </div>
  </div>
</div>

<!-- Report Modal -->
<div class="modal-overlay" id="report-modal">
  <div class="modal" style="max-width:820px">
    <div class="modal-header">
      <span style="font-family:'DM Serif Display',serif;font-size:18px;color:var(--navy)">Generate Report</span>
      <button class="modal-close" onclick="closeReportModal()">✕</button>
    </div>
    <div class="modal-body" id="report-modal-body"></div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeReportModal()">Cancel</button>
      <button class="btn btn-gold" onclick="saveReport()">💾 Save & Generate</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
let clients = [];
let currentClient = null;
let editingClientId = null;
let currentReportClientId = null;

// ── DATA ──────────────────────────────────────────────────────────────────
async function fetchClients() {
  const res = await fetch('/api/clients');
  clients = await res.json();
  renderSidebarClients();
}

async function fetchReports(cid) {
  const res = await fetch(`/api/clients/${cid}/reports`);
  return await res.json();
}

// ── VIEWS ─────────────────────────────────────────────────────────────────
function showView(v, cid) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (v === 'dashboard') {
    document.getElementById('nav-dashboard').classList.add('active');
    renderDashboard();
    setTopbar('Dashboard', 'Overview of all clients and reports', '');
  } else if (v === 'clients') {
    document.getElementById('nav-clients').classList.add('active');
    renderClients();
    setTopbar('All Clients', `${clients.length} clients on retainer`, `<button class="btn btn-primary" onclick="openClientModal()">＋ Add Client</button>`);
  } else if (v === 'client') {
    renderClientDetail(cid);
  }
}

function setTopbar(title, sub, actions) {
  document.getElementById('topbar-title').textContent = title;
  document.getElementById('topbar-sub').textContent = sub;
  document.getElementById('topbar-actions').innerHTML = actions;
}

function renderSidebarClients() {
  const el = document.getElementById('client-list-nav');
  if (clients.length) {
    el.style.display = 'block';
    el.innerHTML = clients.map(c => `
      <div class="client-nav-item" onclick="showView('client','${c.id}')" id="cnav-${c.id}">
        <span>👤</span> ${c.name_1}${c.name_2 ? ' & ' + c.name_2 : ''}
      </div>`).join('');
  }
}

async function renderDashboard() {
  // Calculate the total reports generated this year
  let reportsThisYear = 0;
  const currentYear = new Date().getFullYear();

  for (const client of clients) {
    const res = await fetch(`/api/clients/${client.id}/reports`);
    const reports = await res.json();
    const count = reports.filter(r => r.year === currentYear).length;
    reportsThisYear += count;
  }

  document.getElementById('content').innerHTML = `
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-label">Total Clients</div>
        <div class="stat-value">${clients.length}</div>
        <div class="stat-sub">on retainer</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Reports Generated</div>
        <div class="stat-value">${reportsThisYear}</div>
        <div class="stat-sub">this year</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Next Meetings</div>
        <div class="stat-value">Q${getCurrentQuarter()}</div>
        <div class="stat-sub">${currentYear} cycle</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Time Savings</div>
        <div class="stat-value">~1hr</div>
        <div class="stat-sub">vs full day manually</div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">Clients</span>
        <button class="btn btn-primary btn-sm" onclick="openClientModal()">＋ Add Client</button>
      </div>
      <div class="card-body">
        ${clients.length ? renderClientCards() : '<div class="empty-state"><div class="icon">🏦</div><h3>No clients yet</h3><p>Add your first client to get started.</p></div>'}
      </div>
    </div>`;
}

function getCurrentQuarter() {
  return Math.ceil((new Date().getMonth() + 1) / 3);
}

function renderClients() {
  document.getElementById('content').innerHTML = `
    <div class="card">
      <div class="card-body">
        ${clients.length ? renderClientCards() : '<div class="empty-state"><div class="icon">🏦</div><h3>No clients yet</h3><p>Add your first client to get started.</p></div>'}
      </div>
    </div>`;
}

function renderClientCards() {
  return `<div class="client-grid">${clients.map(c => `
    <div class="client-card" onclick="showView('client','${c.id}')">
      <div class="client-card-initials">${initials(c.name_1)}</div>
      <div class="client-card-name">${c.name_1}${c.name_2 ? ' & ' + c.name_2 : ''}</div>
      <div class="client-card-sub">Monthly Inflow: $${Number(c.monthly_salary||0).toLocaleString()}</div>
      <div class="client-card-meta">
        <span class="tag tag-blue">${c.name_2 ? 'Married' : 'Single'}</span>
        ${(c.retirement_accounts_1||[]).length ? `<span class="tag tag-gold">${(c.retirement_accounts_1||[]).length + (c.retirement_accounts_2||[]).length} Ret. Accts</span>` : ''}
      </div>
    </div>`).join('')}</div>`;
}

function initials(name) {
  return (name || '').split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase();
}

async function renderClientDetail(cid) {
  currentClient = clients.find(c => String(c.id) === String(cid));
  if (!currentClient) return;
  const reports = await fetchReports(cid);
  const name = `${currentClient.name_1}${currentClient.name_2 ? ' & ' + currentClient.name_2 : ''}`;
  setTopbar(name, 'Client profile & report history',
    `<div style="display:flex;gap:10px">
      <button class="btn btn-outline btn-sm" onclick="openClientModal(${cid})">✏️ Edit</button>
      <button class="btn btn-gold" onclick="openReportModal(${cid})">📋 Generate Report</button>
    </div>`);

  document.querySelectorAll('.client-nav-item').forEach(e => e.classList.remove('active'));
  const nav = document.getElementById(`cnav-${cid}`);
  if (nav) nav.classList.add('active');

  document.getElementById('content').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
      <div class="card">
        <div class="card-header"><span class="card-title">Client Information</span></div>
        <div class="card-body">
          ${infoRow('Name', currentClient.name_1)}
          ${currentClient.name_2 ? infoRow('Spouse', currentClient.name_2) : ''}
          ${infoRow('DOB', currentClient.dob_1)}
          ${currentClient.dob_2 ? infoRow('Spouse DOB', currentClient.dob_2) : ''}
          ${infoRow('SSN (last 4)', `xxx-xx-${currentClient.ssn_1||'0000'}`)}
          ${infoRow('Monthly Inflow', '$' + Number(currentClient.monthly_salary||0).toLocaleString())}
          ${infoRow('Monthly Outflow', '$' + Number(currentClient.expense_budget||0).toLocaleString())}
          ${infoRow('Property', currentClient.trust_address || 'N/A')}
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Account Structure</span></div>
        <div class="card-body">
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:8px">${currentClient.name_1} — Retirement</div>
          ${(currentClient.retirement_accounts_1||[]).map(a => `<div style="padding:6px 10px;background:var(--bg);border-radius:6px;margin-bottom:6px;font-size:13px">${a.type}</div>`).join('') || '<div style="color:var(--muted);font-size:13px">None</div>'}
          ${currentClient.name_2 ? `
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin:12px 0 8px">${currentClient.name_2} — Retirement</div>
          ${(currentClient.retirement_accounts_2||[]).map(a => `<div style="padding:6px 10px;background:var(--bg);border-radius:6px;margin-bottom:6px;font-size:13px">${a.type}</div>`).join('') || '<div style="color:var(--muted);font-size:13px">None</div>'}` : ''}
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin:12px 0 8px">Non-Retirement</div>
          ${(currentClient.non_retirement_accounts||[]).map(a => `<div style="padding:6px 10px;background:var(--bg);border-radius:6px;margin-bottom:6px;font-size:13px">${a.type}</div>`).join('') || '<div style="color:var(--muted);font-size:13px">None</div>'}
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">Report History</span>
        <button class="btn btn-gold btn-sm" onclick="openReportModal(${cid})">📋 New Report</button>
      </div>
      <div class="card-body">
        ${reports.length ? reports.map(r => `
          <div class="report-row">
            <div>
              <div style="font-weight:600;font-size:14px">${r.quarter} ${r.year}</div>
              <div style="font-size:12px;color:var(--muted)">${new Date(r.created_at).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})}</div>
            </div>
            <div style="display:flex;gap:8px">
              <a href="/api/reports/${r.id}/sacs.pdf" target="_blank" class="btn btn-outline btn-sm">⬇ SACS</a>
              <a href="/api/reports/${r.id}/tcc.pdf" target="_blank" class="btn btn-outline btn-sm">⬇ TCC</a>
            </div>
          </div>`).join('') : `<div class="empty-state" style="padding:30px"><div class="icon">📄</div><h3>No reports yet</h3><p>Generate the first report for this client.</p></div>`}
      </div>
    </div>`;
}

function infoRow(label, value) {
  return `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px">
    <span style="color:var(--muted)">${label}</span>
    <span style="font-weight:500">${value || '—'}</span>
  </div>`;
}

// ── CLIENT MODAL ──────────────────────────────────────────────────────────
function openClientModal(cid) {
  editingClientId = cid || null;
  const existing = cid ? clients.find(c => String(c.id) === String(cid)) : null;
  document.getElementById('client-modal-title').textContent = cid ? 'Edit Client' : 'Add New Client';
  document.getElementById('client-modal-body').innerHTML = buildClientForm(existing);
  document.getElementById('client-modal').classList.add('open');
  if (existing) {
    renderAccountList('ret1-accounts', existing.retirement_accounts_1||[], 'ret1');
    renderAccountList('ret2-accounts', existing.retirement_accounts_2||[], 'ret2');
    renderAccountList('nonret-accounts', existing.non_retirement_accounts||[], 'nonret');
    renderAccountList('liab-accounts', existing.liabilities||[], 'liab');
    toggleSpouse();
  }
}

function closeClientModal() {
  document.getElementById('client-modal').classList.remove('open');
  editingClientId = null;
}

function buildClientForm(d) {
  d = d || {};
  return `
  <div class="section-divider"><span>Primary Client</span></div>
  <div class="form-grid">
    <div class="form-group">
      <label>Full Name *</label>
      <input id="f-name1" value="${d.name_1||''}" placeholder="e.g. John Smith">
    </div>
    <div class="form-group">
      <label>Date of Birth</label>
      <input id="f-dob1" type="date" value="${d.dob_1||''}">
    </div>
    <div class="form-group">
      <label>SSN (last 4 digits)</label>
      <input id="f-ssn1" maxlength="4" value="${d.ssn_1||''}" placeholder="0000">
    </div>
    <div class="form-group">
      <label>Age</label>
      <input id="f-age1" type="number" value="${d.age_1||''}" placeholder="Auto-calculated">
    </div>
  </div>
  <div class="section-divider"><span>Spouse / Partner (optional)</span></div>
  <div style="margin-bottom:12px;display:flex;align-items:center;gap:8px">
    <input type="checkbox" id="has-spouse" onchange="toggleSpouse()" ${d.name_2 ? 'checked' : ''} style="width:auto;padding:0">
    <label for="has-spouse" style="text-transform:none;letter-spacing:0;color:var(--text);font-size:13.5px;cursor:pointer">This client has a spouse / partner</label>
  </div>
  <div id="spouse-fields" style="display:${d.name_2 ? 'block' : 'none'}">
    <div class="form-grid">
      <div class="form-group">
        <label>Spouse Full Name</label>
        <input id="f-name2" value="${d.name_2||''}" placeholder="e.g. Jane Smith">
      </div>
      <div class="form-group">
        <label>Spouse Date of Birth</label>
        <input id="f-dob2" type="date" value="${d.dob_2||''}">
      </div>
      <div class="form-group">
        <label>Spouse SSN (last 4)</label>
        <input id="f-ssn2" maxlength="4" value="${d.ssn_2||''}" placeholder="0000">
      </div>
      <div class="form-group">
        <label>Spouse Age</label>
        <input id="f-age2" type="number" value="${d.age_2||''}" placeholder="Auto-calculated">
      </div>
    </div>
  </div>
  <div class="section-divider"><span>Financial Setup</span></div>
  <div class="form-grid">
    <div class="form-group">
      <label>Monthly Take-Home (Inflow) *</label>
      <input id="f-salary" type="number" value="${d.monthly_salary||''}" placeholder="15000">
    </div>
    <div class="form-group">
      <label>Monthly Expense Budget (Outflow) *</label>
      <input id="f-expenses" type="number" value="${d.expense_budget||''}" placeholder="11000">
    </div>
    <div class="form-group">
      <label>Private Reserve Target</label>
      <input id="f-pr-target" type="number" value="${d.pr_target||''}" placeholder="Auto: 6mo expenses">
    </div>
    <div class="form-group">
      <label>Trust Property Address</label>
      <input id="f-trust-addr" value="${d.trust_address||''}" placeholder="123 Main St, Atlanta GA">
    </div>
  </div>
  <div class="section-divider"><span>${d.name_1||'Client 1'} — Retirement Accounts</span></div>
  <div id="ret1-accounts"></div>
  <button class="btn-add" onclick="addAccount('ret1')">＋ Add Retirement Account</button>

  <div class="section-divider" id="ret2-section"><span id="ret2-label">${d.name_2||'Spouse'} — Retirement Accounts</span></div>
  <div id="ret2-accounts"></div>
  <button class="btn-add" onclick="addAccount('ret2')">＋ Add Spouse Retirement Account</button>

  <div class="section-divider"><span>Non-Retirement Accounts</span></div>
  <div id="nonret-accounts"></div>
  <button class="btn-add" onclick="addAccount('nonret')">＋ Add Non-Retirement Account</button>

  <div class="section-divider"><span>Liabilities</span></div>
  <div id="liab-accounts"></div>
  <button class="btn-add" onclick="addAccount('liab')">＋ Add Liability</button>
  `;
}

function toggleSpouse() {
  const checked = document.getElementById('has-spouse').checked;
  document.getElementById('spouse-fields').style.display = checked ? 'block' : 'none';
}

const accountTypes = {
  ret1: ['IRA', 'Roth IRA', '401K', 'Pension', '403b', 'SEP IRA'],
  ret2: ['IRA', 'Roth IRA', '401K', 'Pension', '403b', 'SEP IRA'],
  nonret: ['Brokerage', 'Joint Brokerage', 'Schwab Brokerage', 'Money Market', 'Savings'],
  liab: ['Mortgage', 'Auto Loan', 'HELOC', 'Student Loan', 'Personal Loan'],
};

function renderAccountList(containerId, accounts, type) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  accounts.forEach((a, i) => addAccount(type, a));
}

function addAccount(type, existing) {
  const containerId = `${type}-accounts`;
  const el = document.getElementById(containerId);
  const idx = Date.now() + Math.random();
  const opts = accountTypes[type] || [];
  const isLiab = type === 'liab';
  const div = document.createElement('div');
  div.className = 'account-row';
  div.dataset.type = type;
  div.innerHTML = `
    <div class="form-group" style="flex:2">
      <label>Type</label>
      <select class="acct-type">
        ${opts.map(o => `<option ${existing && existing.type===o ? 'selected':''}>${o}</option>`).join('')}
        <option value="custom" ${existing && !opts.includes(existing.type) ? 'selected':''}>Custom...</option>
      </select>
    </div>
    <div class="form-group">
      <label>Acct # (last 4)</label>
      <input class="acct-num" maxlength="4" value="${existing?.acct_num||''}" placeholder="0000">
    </div>
    ${isLiab ? `<div class="form-group"><label>Interest Rate %</label><input class="acct-rate" type="number" step="0.01" value="${existing?.rate||''}" placeholder="3.5"></div>` : ''}
    <button class="btn-icon" onclick="this.parentElement.remove()" title="Remove">✕</button>`;
  el.appendChild(div);
}

function collectAccounts(type) {
  return [...document.querySelectorAll(`#${type}-accounts .account-row`)].map(row => {
    const typeVal = row.querySelector('.acct-type').value;
    const obj = {
      type: typeVal,
      acct_num: row.querySelector('.acct-num')?.value || '',
    };
    const rateEl = row.querySelector('.acct-rate');
    if (rateEl) obj.rate = rateEl.value;
    return obj;
  });
}

async function saveClient() {
  const name1 = document.getElementById('f-name1').value.trim();
  if (!name1) { showToast('Client name is required'); return; }

  const hasSpouse = document.getElementById('has-spouse').checked;
  const data = {
    name_1: name1,
    dob_1: document.getElementById('f-dob1').value,
    ssn_1: document.getElementById('f-ssn1').value,
    age_1: document.getElementById('f-age1').value,
    name_2: hasSpouse ? document.getElementById('f-name2').value : '',
    dob_2: hasSpouse ? document.getElementById('f-dob2').value : '',
    ssn_2: hasSpouse ? document.getElementById('f-ssn2').value : '',
    age_2: hasSpouse ? document.getElementById('f-age2').value : '',
    monthly_salary: document.getElementById('f-salary').value,
    expense_budget: document.getElementById('f-expenses').value,
    pr_target: document.getElementById('f-pr-target').value,
    trust_address: document.getElementById('f-trust-addr').value,
    retirement_accounts_1: collectAccounts('ret1'),
    retirement_accounts_2: collectAccounts('ret2'),
    non_retirement_accounts: collectAccounts('nonret'),
    liabilities: collectAccounts('liab'),
  };

  if (editingClientId) {
    await fetch(`/api/clients/${editingClientId}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
    showToast('Client updated!');
  } else {
    await fetch('/api/clients', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
    showToast('Client added!');
  }
  closeClientModal();
  await fetchClients();
  showView('clients');
}

// ── REPORT MODAL ──────────────────────────────────────────────────────────
async function openReportModal(cid) {
  currentReportClientId = cid;
  const client = clients.find(c => String(c.id) === String(cid));
  const reports = await fetchReports(cid);
  const last = reports[0] || {};
  const lastData = last;

  const salary = Number(client.monthly_salary || 0);
  const expenses = Number(client.expense_budget || 0);
  const prTarget = Number(client.pr_target || expenses * 6);
  const qtr = `Q${getCurrentQuarter()}`;
  const yr = new Date().getFullYear();

  document.getElementById('report-modal-body').innerHTML = `
    <div style="background:var(--navy);border-radius:10px;padding:16px 20px;margin-bottom:20px;display:flex;gap:24px">
      <div><div class="calc-label">Inflow (Salary)</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:20px">$${salary.toLocaleString()}/mo</div></div>
      <div><div class="calc-label">Outflow (Budget)</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:20px">$${expenses.toLocaleString()}/mo</div></div>
      <div><div class="calc-label">Monthly Excess</div><div style="color:#4CAF50;font-family:'DM Serif Display',serif;font-size:20px" id="r-excess-display">$${(salary-expenses).toLocaleString()}/mo</div></div>
      <div><div class="calc-label">Reserve Target</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:20px">$${prTarget.toLocaleString()}</div></div>
    </div>

    <div class="form-grid" style="margin-bottom:16px">
      <div class="form-group">
        <label>Quarter *</label>
        <select id="r-quarter">
          <option ${qtr==='Q1'?'selected':''}>Q1</option>
          <option ${qtr==='Q2'?'selected':''}>Q2</option>
          <option ${qtr==='Q3'?'selected':''}>Q3</option>
          <option ${qtr==='Q4'?'selected':''}>Q4</option>
        </select>
      </div>
      <div class="form-group">
        <label>Year *</label>
        <input id="r-year" type="number" value="${yr}">
      </div>
    </div>

    <div class="report-section">
      <div class="report-section-title">💰 Cash Flow (SACS)</div>
      <div class="form-grid-3">
        <div class="form-group">
          <label>Private Reserve Balance</label>
          <input id="r-pr-balance" type="number" placeholder="0" value="${lastData.private_reserve_balance||''}">
          ${lastData.private_reserve_balance ? `<div class="prev-val">Last: $${Number(lastData.private_reserve_balance).toLocaleString()}</div>` : ''}
        </div>
        <div class="form-group">
          <label>Pinnacle Checking Balance</label>
          <input id="r-pinnacle-checking" type="number" placeholder="0" value="${lastData.pinnacle_checking||''}">
          ${lastData.pinnacle_checking ? `<div class="prev-val">Last: $${Number(lastData.pinnacle_checking).toLocaleString()}</div>` : ''}
        </div>
        <div class="form-group">
          <label>Pinnacle Savings Balance</label>
          <input id="r-pinnacle-savings" type="number" placeholder="0" value="${lastData.pinnacle_savings||''}">
        </div>
        <div class="form-group">
          <label>Schwab Investment Balance</label>
          <input id="r-schwab-balance" type="number" placeholder="0" value="${lastData.schwab_balance||''}">
        </div>
        <div class="form-group">
          <label>Schwab Cash Balance</label>
          <input id="r-schwab-cash" type="number" placeholder="0" value="${lastData.schwab_cash||''}">
        </div>
      </div>
    </div>

    <div class="report-section">
      <div class="report-section-title">🏛 ${client.name_1} — Retirement Accounts</div>
      <div id="r-ret1-balances">
        ${(client.retirement_accounts_1||[]).map((a,i) => `
          <div class="account-row">
            <div style="flex:2;font-weight:500;font-size:13px;padding-bottom:4px">${a.type} (...${a.acct_num||''})</div>
            <div class="form-group" style="flex:1">
              <label>Balance</label>
              <input class="r-ret1-bal" type="number" placeholder="0" data-idx="${i}" value="${(lastData.retirement_1||[])[i]?.balance||''}">
              ${(lastData.retirement_1||[])[i]?.balance ? `<div class="prev-val">Last: $${Number((lastData.retirement_1||[])[i].balance).toLocaleString()}</div>` : ''}
            </div>
          </div>`).join('')}
      </div>
    </div>

    ${client.name_2 ? `<div class="report-section">
      <div class="report-section-title">🏛 ${client.name_2} — Retirement Accounts</div>
      <div id="r-ret2-balances">
        ${(client.retirement_accounts_2||[]).map((a,i) => `
          <div class="account-row">
            <div style="flex:2;font-weight:500;font-size:13px;padding-bottom:4px">${a.type} (...${a.acct_num||''})</div>
            <div class="form-group" style="flex:1">
              <label>Balance</label>
              <input class="r-ret2-bal" type="number" placeholder="0" data-idx="${i}" value="${(lastData.retirement_2||[])[i]?.balance||''}">
            </div>
          </div>`).join('')}
      </div>
    </div>` : ''}

    <div class="report-section">
      <div class="report-section-title">📈 Non-Retirement Accounts</div>
      <div id="r-nonret-balances">
        ${(client.non_retirement_accounts||[]).map((a,i) => `
          <div class="account-row">
            <div style="flex:2;font-weight:500;font-size:13px;padding-bottom:4px">${a.type} (...${a.acct_num||''})</div>
            <div class="form-group">
              <label>Balance</label>
              <input class="r-nonret-bal" type="number" placeholder="0" data-idx="${i}" value="${(lastData.non_retirement||[])[i]?.balance||''}">
            </div>
            <div class="form-group">
              <label>Cash Balance</label>
              <input class="r-nonret-cash" type="number" placeholder="0" data-idx="${i}" value="${(lastData.non_retirement||[])[i]?.cash||''}">
            </div>
          </div>`).join('')}
      </div>
    </div>

    <div class="report-section">
      <div class="report-section-title">🏠 Trust / Property</div>
      <div class="form-grid">
        <div class="form-group">
          <label>Zillow Zestimate (Home Value)</label>
          <input id="r-trust-value" type="number" placeholder="0" value="${lastData.trust_value||''}">
          ${lastData.trust_value ? `<div class="prev-val">Last: $${Number(lastData.trust_value).toLocaleString()}</div>` : ''}
        </div>
        <div class="form-group">
          <label>Property Address</label>
          <input id="r-trust-address" value="${lastData.trust_address || client.trust_address || ''}">
        </div>
      </div>
    </div>

    <div class="report-section">
      <div class="report-section-title">⚠️ Liabilities</div>
      <div id="r-liab-balances">
        ${(client.liabilities||[]).map((a,i) => `
          <div class="account-row">
            <div style="flex:2;font-weight:500;font-size:13px;padding-bottom:4px">${a.type} (${a.rate||'?'}%)</div>
            <div class="form-group" style="flex:1">
              <label>Balance</label>
              <input class="r-liab-bal" type="number" placeholder="0" data-idx="${i}" value="${(lastData.liabilities||[])[i]?.balance||''}">
            </div>
          </div>`).join('')}
      </div>
    </div>

    <!-- Live totals -->
    <div style="background:var(--navy);border-radius:10px;padding:20px;margin-top:8px">
      <div style="color:rgba(255,255,255,0.5);font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:14px">Calculated Totals (TCC)</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px" id="live-totals">
        <div><div class="calc-label">${client.name_1} Retirement</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:18px" id="tot-ret1">$0</div></div>
        ${client.name_2 ? `<div><div class="calc-label">${client.name_2} Retirement</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:18px" id="tot-ret2">$0</div></div>` : ''}
        <div><div class="calc-label">Non-Retirement</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:18px" id="tot-nonret">$0</div></div>
        <div><div class="calc-label">Trust / Property</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:18px" id="tot-trust">$0</div></div>
        <div><div class="calc-label">Grand Total Net Worth</div><div style="color:#4CAF50;font-family:'DM Serif Display',serif;font-size:22px;font-weight:bold" id="tot-grand">$0</div></div>
        <div><div class="calc-label">Liabilities (separate)</div><div style="color:#EF5350;font-family:'DM Serif Display',serif;font-size:18px" id="tot-liab">$0</div></div>
      </div>
    </div>`;

  // Live calculation
  const inputs = document.querySelectorAll('#report-modal-body input[type=number]');
  inputs.forEach(inp => inp.addEventListener('input', updateLiveTotals));
  updateLiveTotals();
  document.getElementById('report-modal').classList.add('open');
}

function updateLiveTotals() {
  const getSum = (cls) => [...document.querySelectorAll(`.${cls}`)].reduce((s,e) => s + (Number(e.value)||0), 0);
  const ret1 = getSum('r-ret1-bal');
  const ret2 = getSum('r-ret2-bal');
  const nonret = getSum('r-nonret-bal');
  const trust = Number(document.getElementById('r-trust-value')?.value||0);
  const liab = getSum('r-liab-bal');
  const grand = ret1 + ret2 + nonret + trust;
  const fmt = v => '$' + Math.round(v).toLocaleString();
  if(document.getElementById('tot-ret1')) document.getElementById('tot-ret1').textContent = fmt(ret1);
  if(document.getElementById('tot-ret2')) document.getElementById('tot-ret2').textContent = fmt(ret2);
  if(document.getElementById('tot-nonret')) document.getElementById('tot-nonret').textContent = fmt(nonret);
  if(document.getElementById('tot-trust')) document.getElementById('tot-trust').textContent = fmt(trust);
  if(document.getElementById('tot-grand')) document.getElementById('tot-grand').textContent = fmt(grand);
  if(document.getElementById('tot-liab')) document.getElementById('tot-liab').textContent = fmt(liab);
}

function closeReportModal() {
  document.getElementById('report-modal').classList.remove('open');
}

async function saveReport() {
  const client = clients.find(c => String(c.id) === String(currentReportClientId));
  const salary = Number(client.monthly_salary||0);
  const expenses = Number(client.expense_budget||0);
  const prTarget = Number(client.pr_target || expenses * 6);

  const getBalances = (cls, accounts, extra) => [...document.querySelectorAll(`.${cls}`)].map((el, i) => {
    const obj = { ...accounts[i], balance: el.value };
    if (extra) {
      const cashEl = document.querySelectorAll(`.${extra}`)[i];
      if (cashEl) obj.cash = cashEl.value;
    }
    return obj;
  });

  const data = {
    quarter: document.getElementById('r-quarter').value,
    year: Number(document.getElementById('r-year').value),
    inflow: salary,
    outflow: expenses,
    private_reserve_target: prTarget,
    private_reserve_balance: document.getElementById('r-pr-balance').value,
    pinnacle_checking: document.getElementById('r-pinnacle-checking').value,
    pinnacle_savings: document.getElementById('r-pinnacle-savings').value,
    schwab_balance: document.getElementById('r-schwab-balance').value,
    schwab_cash: document.getElementById('r-schwab-cash').value,
    trust_value: document.getElementById('r-trust-value').value,
    trust_address: document.getElementById('r-trust-address').value,
    retirement_1: getBalances('r-ret1-bal', client.retirement_accounts_1||[]),
    retirement_2: getBalances('r-ret2-bal', client.retirement_accounts_2||[]),
    non_retirement: getBalances('r-nonret-bal', client.non_retirement_accounts||[], 'r-nonret-cash'),
    liabilities: getBalances('r-liab-bal', client.liabilities||[]),
  };

  const res = await fetch(`/api/clients/${currentReportClientId}/reports`, {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data)
  });
  const { id } = await res.json();
  closeReportModal();
  showToast('Report saved! Downloading PDFs...');
  setTimeout(() => {
    window.open(`/api/reports/${id}/sacs.pdf`, '_blank');
    setTimeout(() => window.open(`/api/reports/${id}/tcc.pdf`, '_blank'), 800);
  }, 300);
  await renderClientDetail(currentReportClientId);
}

// ── UTILS ─────────────────────────────────────────────────────────────────
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

// ── INIT ──────────────────────────────────────────────────────────────────
(async () => {
  await fetchClients();
  showView('dashboard');
})();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
