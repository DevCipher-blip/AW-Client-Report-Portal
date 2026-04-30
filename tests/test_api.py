from io import BytesIO

from pypdf import PdfReader


def make_client(client, **extra):
    return client.post("/api/clients", json={"name_1": "Dana Whitfield", **extra}).get_json()["id"]


def test_blank_balances_still_produce_pdfs(client):
    cid = make_client(client)
    rid = client.post(f"/api/clients/{cid}/reports", json={
        "quarter": "Q2", "year": 2026, "inflow": 9000, "outflow": 6000,
        "private_reserve_balance": "", "trust_value": "",
        "liabilities": [{"type": "Mortgage", "balance": ""}],
    }).get_json()["id"]
    for kind in ("sacs", "tcc"):
        res = client.get(f"/api/reports/{rid}/{kind}.pdf")
        assert res.status_code == 200
        assert len(PdfReader(BytesIO(res.data)).pages) >= 1


def test_report_for_missing_client_is_rejected(client):
    assert client.post("/api/clients/999/reports", json={"quarter": "Q1"}).status_code == 404


def test_update_missing_client_is_404(client):
    assert client.put("/api/clients/999", json={"name_1": "Nobody"}).status_code == 404


def test_non_object_body_is_rejected(client):
    assert client.post("/api/clients", json=["not", "an", "object"]).status_code == 400


def test_reports_list_newest_first_within_quarter(client):
    cid = make_client(client)
    first = client.post(f"/api/clients/{cid}/reports", json={"quarter": "Q1", "year": 2026}).get_json()["id"]
    second = client.post(f"/api/clients/{cid}/reports", json={"quarter": "Q1", "year": 2026}).get_json()["id"]
    ids = [r["id"] for r in client.get(f"/api/clients/{cid}/reports").get_json()]
    assert ids == [second, first]
