"""SQLite storage. Client and report payloads are kept as JSON documents."""

import json
import sqlite3

from flask import current_app, g

SCHEMA = """
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
CREATE INDEX IF NOT EXISTS reports_by_client ON reports(client_id, year);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    with connect(app.config["DATABASE_PATH"]) as conn:
        conn.executescript(SCHEMA)
    conn.close()
    app.teardown_appcontext(close_db)


CLIENTS_WITH_SUMMARY = """
SELECT c.id, c.data, c.updated_at,
    (SELECT COUNT(*) FROM reports r WHERE r.client_id = c.id AND r.year = ?) AS reports_this_year,
    (SELECT r.quarter || ' ' || r.year FROM reports r WHERE r.client_id = c.id
     ORDER BY r.year DESC, r.quarter DESC, r.id DESC LIMIT 1) AS last_report
FROM clients c ORDER BY c.id
"""


def list_clients(year):
    """Clients with the report summary the dashboard needs, in one query."""
    rows = get_db().execute(CLIENTS_WITH_SUMMARY, [year]).fetchall()
    return [
        {
            **json.loads(r["data"]),
            "id": r["id"],
            "updated_at": r["updated_at"],
            "reports_this_year": r["reports_this_year"],
            "last_report": r["last_report"],
        }
        for r in rows
    ]


def get_client(cid):
    row = get_db().execute("SELECT id, data FROM clients WHERE id=?", [cid]).fetchone()
    return {**json.loads(row["data"]), "id": row["id"]} if row else None


def create_client(data):
    conn = get_db()
    cur = conn.execute("INSERT INTO clients (data) VALUES (?)", [json.dumps(data)])
    conn.commit()
    return cur.lastrowid


def update_client(cid, data):
    conn = get_db()
    cur = conn.execute(
        "UPDATE clients SET data=?, updated_at=datetime('now') WHERE id=?", [json.dumps(data), cid]
    )
    conn.commit()
    return cur.rowcount > 0


def delete_client(cid):
    conn = get_db()
    conn.execute("DELETE FROM reports WHERE client_id=?", [cid])
    cur = conn.execute("DELETE FROM clients WHERE id=?", [cid])
    conn.commit()
    return cur.rowcount > 0


def list_reports(cid):
    rows = (
        get_db()
        .execute(
            "SELECT id, quarter, year, report_data, created_at FROM reports "
            "WHERE client_id=? ORDER BY year DESC, quarter DESC, id DESC",
            [cid],
        )
        .fetchall()
    )
    return [
        {
            **json.loads(r["report_data"]),
            "id": r["id"],
            "quarter": r["quarter"],
            "year": r["year"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def create_report(cid, quarter, year, data):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO reports (client_id, quarter, year, report_data) VALUES (?,?,?,?)",
        [cid, quarter, year, json.dumps(data)],
    )
    conn.commit()
    return cur.lastrowid


def get_report_with_client(rid):
    """Return (client, report) for a report id, or None."""
    row = (
        get_db()
        .execute(
            "SELECT r.report_data, c.data FROM reports r JOIN clients c ON r.client_id=c.id WHERE r.id=?",
            [rid],
        )
        .fetchone()
    )
    if not row:
        return None
    return json.loads(row["data"]), json.loads(row["report_data"])
