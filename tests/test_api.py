from io import BytesIO

from pypdf import PdfReader


def make_client(client, **extra):
    return client.post("/api/clients", json={"name_1": "Dana Whitfield", **extra}).get_json()["id"]


def test_blank_balances_still_produce_pdfs(client):
    cid = make_client(client)
    rid = client.post(
        f"/api/clients/{cid}/reports",
        json={
            "quarter": "Q2",
            "year": 2026,
            "inflow": 9000,
            "outflow": 6000,
            "private_reserve_balance": "",
            "trust_value": "",
            "liabilities": [{"type": "Mortgage", "balance": ""}],
        },
    ).get_json()["id"]
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


def test_delete_client_removes_reports(client):
    cid = make_client(client)
    client.post(f"/api/clients/{cid}/reports", json={"quarter": "Q1", "year": 2026})
    assert client.delete(f"/api/clients/{cid}").status_code == 200
    assert client.get(f"/api/clients/{cid}/reports").get_json() == []
    assert client.delete(f"/api/clients/{cid}").status_code == 404


def test_numbers_from_form_strings_are_normalised(client):
    cid = make_client(client, monthly_salary="15000", age_1="54")
    stored = client.get(f"/api/clients/{cid}").get_json()
    assert stored["monthly_salary"] == 15000
    assert stored["age_1"] == 54


def test_client_list_carries_report_summary(client):
    busy = make_client(client)
    make_client(client, name_1="Priya Raman")
    for quarter, year in (("Q1", 2025), ("Q2", 2026), ("Q1", 2026)):
        client.post(f"/api/clients/{busy}/reports", json={"quarter": quarter, "year": year})
    rows = {r["id"]: r for r in client.get("/api/clients?year=2026").get_json()}
    assert rows[busy]["reports_this_year"] == 2
    assert rows[busy]["last_report"] == "Q2 2026"
    others = [r for cid, r in rows.items() if cid != busy]
    assert others[0]["reports_this_year"] == 0
    assert others[0]["last_report"] is None


def test_firm_name_is_configurable(tmp_path):
    from portal import create_app

    app = create_app({"DATABASE_PATH": str(tmp_path / "p.db"), "FIRM_NAME": "Harbor & Pine Advisors"})
    web = app.test_client()
    assert "Harbor &amp; Pine Advisors" in web.get("/").get_data(as_text=True)
    cid = web.post("/api/clients", json={"name_1": "Dana"}).get_json()["id"]
    rid = web.post(f"/api/clients/{cid}/reports", json={"quarter": "Q1", "year": 2026}).get_json()["id"]
    text = PdfReader(BytesIO(web.get(f"/api/reports/{rid}/tcc.pdf").data)).pages[0].extract_text()
    assert "Harbor & Pine Advisors" in text
