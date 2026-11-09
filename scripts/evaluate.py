import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings, get_settings
from app.corpus import load_cards
from app.db import Case, LLMCall
from app.main import COOKIE, create_app
from app.verify import verify_points

HEADERS = {"x-nyaya-client": "web"}
MOCK_ONLY = {"dropped_min", "rejected_paragraphs_min", "hedge", "calls_max"}
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
FROZEN_TODAY = date(2026, 11, 9)


def last_assistant(case: dict) -> dict:
    for m in reversed(case["messages"]):
        if m["role"] == "assistant":
            return m
    return {"content": "", "meta": {}}


def last_user(case: dict) -> dict:
    for m in reversed(case["messages"]):
        if m["role"] == "user":
            return m
    return {"meta": {}}


def reply_text(msg: dict) -> str:
    blocks = (msg.get("meta") or {}).get("blocks") or {}
    extra = blocks.get("draft", {}).get("preview", "")
    return f"{msg.get('content', '')}\n{extra}"


def check(expect: dict, case: dict, calls: list[dict], live: bool) -> list[dict]:
    msg = last_assistant(case)
    meta = msg.get("meta") or {}
    blocks = meta.get("blocks") or {}
    cited = [c["id"] for c in meta.get("citations") or []]
    text = reply_text(msg)
    facts = {f["field"]: f["value"] for f in case["facts"]}
    results = []

    def rec(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": detail})

    for key, want in expect.items():
        if live and key in MOCK_ONLY:
            continue
        if key == "domain":
            rec(key, case["domain"] == want, case["domain"])
        elif key == "mode":
            rec(key, msg.get("mode") == want, msg.get("mode"))
        elif key == "language":
            rec(key, case["language"] == want, case["language"])
        elif key == "cites_include":
            missing = [w for w in want if w not in cited]
            rec(key, not missing, f"cited {cited}; missing {missing}")
        elif key == "cites_exclude":
            bad = [w for w in want if w in cited]
            rec(key, not bad, f"cited {cited}")
        elif key == "dropped_min":
            rec(key, meta.get("dropped", 0) >= want, f"dropped {meta.get('dropped', 0)}")
        elif key == "facts":
            wrong = {k: facts.get(k) for k, v in want.items() if facts.get(k) != v}
            rec(key, not wrong, f"mismatched {wrong}")
        elif key == "reply_contains":
            missing = [w for w in want if w.lower() not in text.lower()]
            rec(key, not missing, f"missing {missing}")
        elif key == "reply_excludes":
            found = [w for w in want if w.lower() in text.lower()]
            rec(key, not found, f"found {found}")
        elif key == "notes_contains":
            notes = " ".join(blocks.get("notes") or [])
            missing = [w for w in want if w.lower() not in notes.lower()]
            rec(key, not missing, f"missing {missing}")
        elif key == "question":
            rec(key, bool(blocks.get("question")) == want, blocks.get("question", ""))
        elif key == "pending":
            rec(key, (case.get("pending") is not None) == want, "pending" if case.get("pending") else "none")
        elif key == "draft":
            rec(key, bool(blocks.get("draft")) == want)
        elif key == "draft_contains":
            preview = blocks.get("draft", {}).get("preview", "")
            missing = [w for w in want if w not in preview]
            rec(key, not missing, f"missing {missing}")
        elif key == "draft_excludes":
            preview = blocks.get("draft", {}).get("preview", "")
            found = [w for w in want if w in preview]
            rec(key, not found, f"found {found}")
        elif key == "rejected_paragraphs_min":
            n = blocks.get("draft", {}).get("rejected", 0)
            rec(key, n >= want, f"rejected {n}")
        elif key == "canned":
            rec(key, blocks.get("canned") == want, blocks.get("canned"))
        elif key == "hedge":
            rec(key, bool(blocks.get("hedge")) == want, blocks.get("hedge", ""))
        elif key == "practice":
            rec(key, bool(blocks.get("practice")) == want)
        elif key == "notice_kind":
            kind = (case.get("notice") or {}).get("kind")
            rec(key, kind == want, kind)
        elif key == "deadline":
            got = (case.get("notice") or {}).get("deadline", "")
            rec(key, got == want, got)
        elif key == "risks_include":
            missing = [w for w in want if w not in (meta.get("risks") or [])]
            rec(key, not missing, f"risks {meta.get('risks')}")
        elif key == "devanagari":
            rec(key, bool(DEVANAGARI.search(msg.get("content", ""))) == want)
        elif key == "calls_max":
            rec(key, len(calls) <= want, f"{len(calls)} calls")
        elif key == "via":
            rec(key, (last_user(case).get("meta") or {}).get("via") == want)
        else:
            rec(key, False, "unknown expectation")
    return results


def universal(case: dict, cards: dict) -> list[dict]:
    msg = last_assistant(case)
    meta = msg.get("meta") or {}
    blocks = meta.get("blocks") or {}
    out = []
    citations = meta.get("citations") or []
    unknown = [c["id"] for c in citations if c["id"] not in cards]
    out.append({"check": "citations_exist", "ok": not unknown, "detail": f"unknown {unknown}"})
    if blocks.get("points"):
        by_n = {c["n"]: c["id"] for c in citations}
        points = [{"text": p["text"], "sources": [by_n[r] for r in p["refs"] if r in by_n]} for p in blocks["points"]]
        facts = {f["field"]: {"value": f["value"]} for f in case["facts"]}
        verdict = verify_points(points, cards, facts)
        out.append({"check": "displayed_points_reverify", "ok": not verdict.dropped,
                    "detail": [d["issues"] for d in verdict.dropped]})
    return out


def calls_for(client, app, since_id: int) -> list[dict]:
    token = client.cookies.get(COOKIE)
    th = hashlib.sha256(token.encode()).hexdigest()

    async def fetch():
        async with app.state.sessions() as s:
            case_id = (await s.execute(select(Case.id).where(Case.token_hash == th))).scalar_one()
            rows = (await s.execute(select(LLMCall).where(LLMCall.case_id == case_id, LLMCall.id > since_id)
                                    .order_by(LLMCall.id))).scalars().all()
            return [{"id": r.id, "node": r.node, "provider": r.provider, "model": r.model, "input_tokens": r.input_tokens,
                     "output_tokens": r.output_tokens, "latency_ms": r.latency_ms, "ok": r.ok, "error": r.error} for r in rows]

    return client.portal.call(fetch)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the scripted test cases and save raw outputs")
    parser.add_argument("--live", action="store_true", help="use the configured LLM provider instead of the scripted mock")
    parser.add_argument("--cases", default=str(ROOT / "tests" / "cases.json"))
    parser.add_argument("--out", default=str(ROOT / "raw_outputs"))
    parser.add_argument("--only", nargs="*", help="case ids to run")
    args = parser.parse_args()

    if args.live:
        settings = get_settings()
        if settings.llm_provider == "mock":
            print("LLM_PROVIDER is mock; set a real provider in .env for --live", file=sys.stderr)
            return 2
        app = create_app(settings)
        label = f"live_{settings.llm_provider}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        base = get_settings()
        settings = Settings(database_url=base.database_url, llm_provider="mock", stt_provider="mock",
                            mock_fixtures=str(ROOT / "tests" / "mock_llm.json"), embedding_provider="none",
                            max_calls_per_day=100000)
        app = create_app(settings, today=lambda: FROZEN_TODAY)
        label = "mock"

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]
    cards = {c["id"]: {k: (v.isoformat() if isinstance(v, date) else v) for k, v in c.items()} for c in load_cards()}
    out_dir = Path(args.out) / label
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"run": label, "provider": settings.llm_provider, "model": settings.resolved_model,
               "started": datetime.now().isoformat(timespec="seconds"), "cases": []}
    node_counter, tokens_in, tokens_out, latencies = Counter(), 0, 0, []

    with TestClient(app) as client:
        for case in cases:
            client.cookies.clear()
            client.post("/api/case", headers=HEADERS)
            last_call = 0
            record = {"id": case["id"], "about": case["about"], "turns": []}
            case_ok = True
            for i, turn in enumerate(case["turns"]):
                if args.live and "voice" in turn:
                    record["turns"].append({"skipped": "scripted audio is only meaningful with the mock transcriber"})
                    continue
                started = time.perf_counter()
                if "confirm" in turn:
                    r = client.post("/api/case/confirm", json=turn["confirm"], headers=HEADERS)
                    sent = {"confirm": turn["confirm"]}
                elif "voice" in turn:
                    r = client.post("/api/case/voice", headers=HEADERS,
                                    files={"audio": ("voice.webm", turn["voice"].encode(), "audio/webm")},
                                    data={"mode": turn.get("mode", "auto"), "language": turn.get("language", "auto")})
                    sent = {"voice_bytes": len(turn["voice"]), "mode": turn.get("mode", "auto")}
                else:
                    sent = {"text": turn["text"], "mode": turn.get("mode", "auto"), "language": turn.get("language", "auto")}
                    r = client.post("/api/case/messages", json=sent, headers=HEADERS)
                elapsed = int((time.perf_counter() - started) * 1000)
                calls = calls_for(client, app, last_call)
                if calls:
                    last_call = calls[-1]["id"]
                for c in calls:
                    node_counter[c["node"]] += 1
                    tokens_in += c["input_tokens"]
                    tokens_out += c["output_tokens"]
                    latencies.append(c["latency_ms"])
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text}
                entry = {"turn": i + 1, "sent": sent, "status": r.status_code, "elapsed_ms": elapsed, "llm_calls": calls}
                if r.status_code == 200:
                    c = body["case"]
                    entry["assistant"] = last_assistant(c)
                    entry["case_after"] = {k: c[k] for k in ("domain", "language", "facts", "missing", "events", "notice", "pending")}
                    entry["checks"] = check(turn.get("expect", {}), c, calls, args.live) + universal(c, cards)
                    draft = (entry["assistant"].get("meta") or {}).get("blocks", {}).get("draft")
                    if draft:
                        (out_dir / f"{case['id']}_draft_{draft['id']}.txt").write_text(draft["preview"], encoding="utf-8")
                else:
                    entry["error"] = body
                    entry["checks"] = [{"check": "http_200", "ok": False, "detail": r.status_code}]
                if not all(x["ok"] for x in entry["checks"]):
                    case_ok = False
                record["turns"].append(entry)
            record["passed"] = case_ok
            (out_dir / f"{case['id']}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            failed = [f"turn {t['turn']}: {x['check']} ({x['detail']})" for t in record["turns"] if "checks" in t
                      for x in t["checks"] if not x["ok"]]
            summary["cases"].append({"id": case["id"], "passed": case_ok, "failed_checks": failed})
            print(f"{'PASS' if case_ok else 'FAIL'}  {case['id']}" + ("" if case_ok else f"  {failed}"))

    summary["passed"] = sum(c["passed"] for c in summary["cases"])
    summary["total"] = len(summary["cases"])
    summary["llm_calls_by_node"] = dict(node_counter)
    summary["tokens"] = {"input": tokens_in, "output": tokens_out}
    if latencies:
        latencies.sort()
        summary["latency_ms"] = {"median": latencies[len(latencies) // 2], "p90": latencies[int(len(latencies) * 0.9) - 1]}
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{summary['passed']}/{summary['total']} cases passed. Raw outputs in {out_dir}")
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
