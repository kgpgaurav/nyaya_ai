import io
import zipfile
from datetime import date

from docx import Document as DocxDocument

from conftest import HEADERS

D1 = "My landlord Mr. Sharma in Pune has not returned my deposit of Rs 50,000. I moved out on 31 August 2026 and gave back the keys. What are my options?"
D2 = "It's in Maharashtra. We signed a leave and licence agreement which says the deposit is refundable on vacating."
D3 = "Please draft a letter asking for the full Rs 50,000 back"


def say(client, text, mode="auto"):
    return client.post("/api/case/messages", json={"text": text, "mode": mode}, headers=HEADERS)


def draft_case(client):
    for text, mode in ((D1, "auto"), (D2, "auto"), (D3, "draft")):
        assert say(client, text, mode).status_code == 200
    r = client.post("/api/case/confirm", json={"confirmed": True, "edits": {}}, headers=HEADERS)
    assert r.status_code == 200
    return r.json()["case"]["documents"][0]["id"]


def test_mutations_need_client_header_and_same_origin(client):
    assert client.post("/api/case/messages", json={"text": "hi"}).status_code == 403
    r = client.post("/api/case/messages", json={"text": "hi"}, headers={**HEADERS, "origin": "https://evil.example"})
    assert r.status_code == 403


def test_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_no_case_is_401(make_client):
    c = make_client()
    assert c.get("/api/case").status_code == 401
    assert say(c, "hello").status_code == 401


def test_unknown_scripted_message_is_502_and_case_unchanged(client):
    r = say(client, "a message the mock has never seen")
    assert r.status_code == 502
    case = client.get("/api/case").json()["case"]
    assert case["messages"] == [] and case["facts"] == []


def test_model_not_configured_is_503(make_client):
    c = make_client(llm_provider="groq", groq_api_key="", stt_provider="none")
    c.post("/api/case", headers=HEADERS)
    r = say(c, "hello")
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["detail"]
    assert c.get("/api/config").json()["llm_ready"] is False


def test_case_budget(make_client):
    c = make_client(max_calls_per_case=3)
    c.post("/api/case", headers=HEADERS)
    assert say(c, D1).status_code == 200
    assert say(c, D2).status_code == 429


def test_confirm_without_pending_is_409(client):
    assert client.post("/api/case/confirm", json={"confirmed": True}, headers=HEADERS).status_code == 409


def test_new_message_cancels_pending_confirmation(client):
    for text, mode in ((D1, "auto"), (D2, "auto"), (D3, "draft")):
        say(client, text, mode)
    assert client.get("/api/case").json()["case"]["pending"]
    r = say(client, D2)
    assert r.status_code == 200
    assert r.json()["case"]["pending"] is None


def test_draft_downloads_and_isolation(client, make_client):
    doc_id = draft_case(client)
    txt = client.get(f"/api/case/documents/{doc_id}.txt")
    assert txt.status_code == 200 and "Rs 50,000" in txt.text
    docx = client.get(f"/api/case/documents/{doc_id}.docx")
    assert docx.status_code == 200
    assert zipfile.is_zipfile(io.BytesIO(docx.content))
    body = "\n".join(p.text for p in DocxDocument(io.BytesIO(docx.content)).paragraphs)
    assert "Mr. Sharma" in body and "18%" not in body
    other = make_client()
    other.post("/api/case", headers=HEADERS)
    assert other.get(f"/api/case/documents/{doc_id}.txt").status_code == 404


def test_confirm_edits_are_applied_and_marked(client):
    for text, mode in ((D1, "auto"), (D2, "auto"), (D3, "draft")):
        say(client, text, mode)
    r = client.post("/api/case/confirm", json={"confirmed": True, "edits": {"landlord": "Mr. R. Sharma", "salary": "x"}},
                    headers=HEADERS)
    facts = {f["field"]: f for f in r.json()["case"]["facts"]}
    assert facts["landlord"]["value"] == "Mr. R. Sharma" and facts["landlord"]["edited"]
    assert all(f["confirmed"] for f in facts.values())
    assert "salary" not in facts


def test_cancel_confirmation(client):
    for text, mode in ((D1, "auto"), (D2, "auto"), (D3, "draft")):
        say(client, text, mode)
    r = client.post("/api/case/confirm", json={"confirmed": False}, headers=HEADERS)
    case = r.json()["case"]
    assert case["documents"] == [] and case["pending"] is None
    assert case["messages"][-1]["meta"]["blocks"]["canned"] == "draft_cancelled"


def test_state_survives_app_restart(make_client):
    a = make_client()
    a.post("/api/case", headers=HEADERS)
    say(a, D1)
    cookie = dict(a.cookies)
    b = make_client()
    b.cookies.update(cookie)
    case = b.get("/api/case").json()["case"]
    assert {f["field"] for f in case["facts"]} >= {"landlord", "deposit_amount"}
    assert say(b, D2).status_code == 200


def test_delete_removes_case_and_checkpoints(client):
    say(client, D1)
    cookie = dict(client.cookies)
    assert client.delete("/api/case", headers=HEADERS).json() == {"deleted": True}
    client.cookies.update(cookie)
    assert client.get("/api/case").status_code == 401


def test_voice_unknown_audio_is_502(client):
    r = client.post("/api/case/voice", headers=HEADERS, files={"audio": ("v.webm", b"unknown", "audio/webm")})
    assert r.status_code == 502


def test_expired_sources_are_withheld(make_client):
    c = make_client(today=date(2027, 3, 1))
    c.post("/api/case", headers=HEADERS)
    r = say(c, D1)
    msg = r.json()["case"]["messages"][-1]
    cited = [x["id"] for x in msg["meta"]["citations"]]
    assert "MTA-11" not in cited
    assert any("review date" in n for n in msg["meta"]["blocks"]["notes"])


def test_sources_endpoint_lists_corpus(client):
    cards = client.get("/api/sources").json()
    assert {c["id"] for c in cards} >= {"COW-17", "MTA-11", "NIA-138", "LSA-12"}
    assert all(c["review_by"] and c["url"].startswith("https://") for c in cards)


def test_export_is_json(client):
    say(client, D1)
    r = client.get("/api/case/export")
    assert r.status_code == 200 and r.json()["domain"] == "deposit"
