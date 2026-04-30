import base64

import pytest

from portal import create_app


def make_client(client, **extra):
    res = client.post("/api/clients", json={"name_1": "Dana Whitfield", **extra})
    assert res.status_code == 200, res.get_json()
    return res.get_json()["id"]


def test_sql_metacharacters_are_stored_as_data(client):
    cid = make_client(client, name_1="Robert'); DROP TABLE clients;--")
    assert client.get(f"/api/clients/{cid}").get_json()["name_1"] == "Robert'); DROP TABLE clients;--"
    assert len(client.get("/api/clients").get_json()) == 1


@pytest.mark.parametrize("ssn", ["123-45-6789", "123456789", "12a4"])
def test_full_ssn_is_rejected(client, ssn):
    res = client.post("/api/clients", json={"name_1": "Dana", "ssn_1": ssn})
    assert res.status_code == 400
    assert "ssn_1" in res.get_json()["fields"]


def test_full_account_number_is_rejected(client):
    res = client.post(
        "/api/clients",
        json={"name_1": "Dana", "retirement_accounts_1": [{"type": "IRA", "acct_num": "998877"}]},
    )
    assert res.status_code == 400
    assert "retirement_accounts_1.acct_num" in res.get_json()["fields"]


def test_unknown_keys_are_dropped(client):
    cid = make_client(client, is_admin=True, notes="<script>alert(1)</script>")
    stored = client.get(f"/api/clients/{cid}").get_json()
    assert "is_admin" not in stored and "notes" not in stored


def test_report_quarter_and_year_are_validated(client):
    cid = make_client(client)
    assert client.post(f"/api/clients/{cid}/reports", json={"quarter": "Q9", "year": 2026}).status_code == 400
    assert (
        client.post(f"/api/clients/{cid}/reports", json={"quarter": "Q1", "year": "1e9"}).status_code == 400
    )
    assert client.post(f"/api/clients/{cid}/reports", json={"quarter": "Q1", "year": 2026}).status_code == 200


def test_cross_site_write_is_refused(client):
    res = client.post("/api/clients", json={"name_1": "Mallory"}, headers={"Origin": "https://evil.example"})
    assert res.status_code == 403
    res = client.delete("/api/clients/1", headers={"Sec-Fetch-Site": "cross-site"})
    assert res.status_code == 403
    assert client.get("/api/clients").get_json() == []


def test_same_origin_write_is_allowed(client):
    res = client.post(
        "/api/clients",
        json={"name_1": "Dana"},
        headers={"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"},
    )
    assert res.status_code == 200


def test_form_encoded_post_is_not_accepted(client):
    res = client.post("/api/clients", data={"name_1": "Mallory"})
    assert res.status_code == 400


def test_pdf_filename_cannot_carry_path_or_header_characters(client):
    cid = make_client(client, name_1='../../etc/passwd"\r\nX-Evil: 1')
    rid = client.post(f"/api/clients/{cid}/reports", json={"quarter": "Q1", "year": 2026}).get_json()["id"]
    res = client.get(f"/api/reports/{rid}/sacs.pdf")
    assert res.status_code == 200
    disposition = res.headers["Content-Disposition"]
    assert disposition == "inline; filename=SACS_etc-passwd-X-Evil-1_Q12026.pdf"
    assert "X-Evil" not in res.headers


def test_security_headers_and_no_store(client):
    res = client.get("/api/clients")
    assert res.headers["Cache-Control"] == "no-store"
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"


@pytest.fixture
def locked(tmp_path):
    app = create_app({"DATABASE_PATH": str(tmp_path / "p.db"), "PORTAL_PASSWORD": "correct horse"})
    return app.test_client()


def basic(user, password):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


def test_login_required_when_password_set(locked):
    assert locked.get("/").status_code == 401
    assert locked.get("/api/clients", headers=basic("admin", "wrong")).status_code == 401
    assert locked.get("/api/clients", headers=basic("admin", "correct horse")).status_code == 200


def test_healthcheck_stays_open_behind_login(locked):
    assert locked.get("/healthz").status_code == 200
