import json
from pathlib import Path

import pytest

from conftest import HEADERS
from evaluate import calls_for, check, universal
from app.corpus import load_cards

CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
CARDS = {c["id"]: {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in c.items()} for c in load_cards()}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_scenario(client, case):
    last = 0
    for i, turn in enumerate(case["turns"]):
        if "confirm" in turn:
            r = client.post("/api/case/confirm", json=turn["confirm"], headers=HEADERS)
        elif "voice" in turn:
            r = client.post("/api/case/voice", headers=HEADERS,
                            files={"audio": ("v.webm", turn["voice"].encode(), "audio/webm")},
                            data={"mode": turn["mode"], "language": turn["language"]})
        else:
            r = client.post("/api/case/messages", json={k: turn[k] for k in ("text", "mode", "language")}, headers=HEADERS)
        assert r.status_code == 200, r.text
        calls = calls_for(client, client.app, last)
        if calls:
            last = calls[-1]["id"]
        results = check(turn["expect"], r.json()["case"], calls, live=False) + universal(r.json()["case"], CARDS)
        failed = [x for x in results if not x["ok"]]
        assert not failed, f"turn {i + 1}: {failed}"
