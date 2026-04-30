from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, send_file

from . import db
from .pdf import build_sacs_pdf, build_tcc_pdf

bp = Blueprint("portal", __name__)


def json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def bad_body():
    return jsonify({"error": "expected a JSON object"}), 400


def not_found():
    return jsonify({"error": "not found"}), 404


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/api/clients")
def list_clients():
    return jsonify(db.list_clients())


@bp.post("/api/clients")
def create_client():
    data = json_object()
    if data is None:
        return bad_body()
    return jsonify({**data, "id": db.create_client(data)})


@bp.get("/api/clients/<int:cid>")
def get_client(cid):
    client = db.get_client(cid)
    return jsonify(client) if client else not_found()


@bp.put("/api/clients/<int:cid>")
def update_client(cid):
    data = json_object()
    if data is None:
        return bad_body()
    if not db.update_client(cid, data):
        return not_found()
    return jsonify({**data, "id": cid})


@bp.delete("/api/clients/<int:cid>")
def delete_client(cid):
    db.delete_client(cid)
    return jsonify({"ok": True})


@bp.get("/api/clients/<int:cid>/reports")
def list_reports(cid):
    return jsonify(db.list_reports(cid))


@bp.post("/api/clients/<int:cid>/reports")
def save_report(cid):
    data = json_object()
    if data is None:
        return bad_body()
    if not db.get_client(cid):
        return not_found()
    quarter = data.get("quarter", "Q1")
    year = data.get("year", datetime.now().year)
    return jsonify({"id": db.create_report(cid, quarter, year, data)})


def pdf_response(rid, prefix, builder):
    found = db.get_report_with_client(rid)
    if not found:
        return "Not found", 404
    client, report = found
    name = (
        f"{prefix}_{client.get('name_1', 'Client')}_{report.get('quarter', '')}{report.get('year', '')}.pdf"
    )
    return send_file(builder(client, report), mimetype="application/pdf", download_name=name)


@bp.get("/api/reports/<int:rid>/sacs.pdf")
def download_sacs(rid):
    return pdf_response(rid, "SACS", build_sacs_pdf)


@bp.get("/api/reports/<int:rid>/tcc.pdf")
def download_tcc(rid):
    return pdf_response(rid, "TCC", build_tcc_pdf)
