import json
import uuid

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from .. import corpus
from ..db import Document
from ..domains import DOMAIN_FIELDS, LANGS, OPPONENT, draft_missing, field_names, next_question, spec
from ..drafts import DOCS, doc_lang, fallback_paragraphs, render
from ..provenance import grounded, merge_extraction, norm
from ..rules import detect_script, rule_risks
from ..schemas import Answer, DraftNarrative, Extraction, NoticeReading, PracticeTurn, Triage
from ..texts import NOTICE_KINDS, t
from ..verify import Evidence, problems_in, roleplay_issues, verify_plain, verify_points
from .prompts import COMPOSE, COMPOSE_MODES, COMPOSE_RETRY, DRAFT, EXTRACT, LANG_NAME, NOTICE, PRACTICE, TRIAGE
from .state import PER_TURN_RESET, CaseState, Ctx

LAWYER_RISKS = ("criminal", "police", "family", "court_deadline")
SERIOUS_NOTICES = {"court_summons", "police", "cheque_bounce", "legal_notice", "tax", "bank_recovery"}
NOTICE_CARDS = {"cheque_bounce": ["NIA-138"], "police": ["BNSS"]}
INTENT_MODE = {"build_case": "build_case", "explain": "explain", "draft": "draft", "practice": "practice", "notice": "notice", "chat": "build_case"}


def payload(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False, default=str)


def fact_values(facts: dict) -> dict:
    return {k: v["value"] for k, v in facts.items()}


def cards_for_prompt(cards: list[dict], lang: str) -> list[dict]:
    key = "summary_hi" if lang == "hi" else "summary_en"
    return [{"id": c["id"], "citation": c["citation"], "text": c[key], "caveat": c.get("caveat", "")} for c in cards]


def citation_meta(cards: list[dict], lang: str) -> list[dict]:
    key = "summary_hi" if lang == "hi" else "summary_en"
    return [
        {
            "n": i + 1,
            "id": c["id"],
            "title": c["title"],
            "citation": c["citation"],
            "summary": c[key],
            "url": c["url"],
            "locator": c.get("locator", ""),
            "reviewed_on": str(c.get("reviewed_on", "")),
            "caveat": c.get("caveat", ""),
        }
        for i, c in enumerate(cards)
    ]


def with_assistant(state: CaseState, reply: str) -> list:
    return (state.get("history") or []) + [{"role": "assistant", "content": reply}]


async def ingest(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    message = norm(state["message"])
    pref = state.get("language_pref") or "auto"
    language = pref if pref in LANGS else detect_script(message)
    history = (state.get("history") or []) + [{"role": "user", "content": message}]
    return {
        **PER_TURN_RESET,
        "message": message,
        "turn": (state.get("turn") or 0) + 1,
        "language": language,
        "history": history[-12:],
        "facts": state.get("facts") or {},
        "events": state.get("events") or [],
        "domain": state.get("domain") or "unknown",
        "practice_log": state.get("practice_log") or [],
    }


async def guard(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    ctx = runtime.context
    message = state["message"]
    triage = await ctx.llm.structured(
        "triage",
        Triage,
        TRIAGE,
        payload(current_domain=state["domain"], recent_history=state["history"][-7:-1], CURRENT_MESSAGE=message),
        ctx.recorder,
        key=message,
    )
    risks = set(triage.risks)
    soft = set()
    for risk in rule_risks(message):
        if risk in ("danger", "fabrication"):
            risks.add(risk)
        elif risk in LAWYER_RISKS and risk not in risks:
            soft.add(risk)

    requested = state.get("requested_mode") or "auto"
    domain = state["domain"]
    if triage.domain != "unknown" and not (triage.domain == "other" and domain in DOMAIN_FIELDS and triage.intent == "chat"):
        domain = triage.domain
    if requested == "notice" and domain in ("unknown", "other"):
        domain = "notice"
    language = state["language"] if (state.get("language_pref") or "auto") in LANGS else triage.language

    mode = requested if requested != "auto" else INTENT_MODE[triage.intent]
    if domain == "notice" and mode in ("build_case", "explain", "draft", "practice"):
        mode = "notice"

    canned = ""
    if "danger" in risks:
        canned = "danger"
    elif "fabrication" in risks:
        canned = "fabrication"
    elif mode == "notice":
        canned = ""
    elif risks & set(LAWYER_RISKS):
        canned = "needs_lawyer"
    elif domain == "other":
        canned = "out_of_scope"
    elif domain == "unknown":
        canned = "welcome"
    elif mode == "practice" and domain not in OPPONENT:
        canned = "practice_unavailable"

    return {
        "domain": domain,
        "intent": triage.intent,
        "risks": sorted(risks),
        "soft_risks": sorted(soft),
        "language": language,
        "mode": mode,
        "canned": canned,
    }


def after_guard(state: CaseState) -> str:
    if state["canned"]:
        return "canned"
    if state["mode"] == "notice":
        return "notice"
    if state["mode"] == "practice":
        return "practice"
    return "extract"


async def extract(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    ctx = runtime.context
    domain, lang, message = state["domain"], state["language"], state["message"]
    fields = "\n".join(f"- {f.name}: {f.label['en']}" for f in DOMAIN_FIELDS[domain])
    extraction = await ctx.llm.structured(
        "extract",
        Extraction,
        EXTRACT.format(domain=domain, fields=fields),
        payload(existing_facts=fact_values(state["facts"]), CURRENT_MESSAGE=message),
        ctx.recorder,
        key=message,
    )
    facts, events, dropped, conflicts = merge_extraction(
        domain, extraction, message, state["facts"], state["events"], state["turn"]
    )
    notes = list(state.get("notes") or [])
    if dropped:
        notes.append(t("dropped_fact", lang))
    for c in conflicts:
        notes.append(t("conflict", lang, field=spec(domain, c["field"]).label[lang], old=c["old"], new=c["new"]))
    mode = state["mode"]
    if mode == "draft":
        missing = draft_missing(domain, facts)
        if missing:
            labels = ", ".join(spec(domain, m).label[lang] for m in missing)
            notes.append(t("draft_needs", lang, fields=labels))
            mode = "build_case"
    if "commercial" in state["risks"] and domain == "refund":
        notes.append(t("commercial", lang))
    return {"facts": facts, "events": events, "notes": notes, "conflicts": conflicts, "mode": mode}


def after_extract(state: CaseState) -> str:
    return "draft" if state["mode"] == "draft" else "retrieve"


async def retrieve(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    ctx = runtime.context
    query = " ".join([state["message"], *fact_values(state["facts"]).values()])
    async with ctx.sessions() as session:
        cards, expired = await corpus.retrieve(session, state["domain"], query, ctx.today, embedder=ctx.embedder)
    notes = list(state.get("notes") or [])
    if expired:
        notes.append(t("expired_sources", state["language"]))
    return {"sources": [corpus.serialisable(c) for c in cards], "expired": expired, "notes": notes}


async def compose(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    ctx = runtime.context
    lang, mode = state["language"], state["mode"]
    system = COMPOSE.format(
        lang=LANG_NAME[lang], max_points=4 if mode == "build_case" else 5, mode_rules=COMPOSE_MODES.get(mode, COMPOSE_MODES["explain"])
    )
    node = "compose"
    if state.get("attempts"):
        issues = "\n".join(f"- {i}" for d in state.get("dropped", []) for i in d["issues"])
        system += "\n\n" + COMPOSE_RETRY.format(issues=issues)
        node = "compose_retry"
    answer = await ctx.llm.structured(
        node,
        Answer,
        system,
        payload(
            facts=fact_values(state["facts"]),
            question=state["message"],
            SOURCE_CARDS=cards_for_prompt(state["sources"], lang),
        ),
        ctx.recorder,
        key=state["message"],
    )
    return {"points": [p.model_dump() for p in answer.points]}


async def verify(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    retrieved = {c["id"]: c for c in state["sources"]}
    verdict = verify_points(state["points"], retrieved, state["facts"])
    dropped = list(state.get("dropped") or []) + verdict.dropped
    if not verdict.ok and not state.get("attempts"):
        return {"dropped": dropped, "attempts": 1, "points": [], "retry": True}
    return {"dropped": dropped, "points": verdict.kept, "retry": False}


def after_verify(state: CaseState) -> str:
    return "compose" if state.get("retry") else "respond"


async def respond(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    lang, domain, mode = state["language"], state["domain"], state["mode"]
    cards = {c["id"]: c for c in state["sources"]}
    order: list[str] = []
    points = []
    for p in state["points"]:
        refs = []
        for s in p["sources"]:
            if s not in order:
                order.append(s)
            refs.append(order.index(s) + 1)
        points.append({"text": p["text"], "refs": refs})
    notes = list(state.get("notes") or [])
    for r in state.get("soft_risks") or []:
        notes.append(t("needs_lawyer", lang, what=t(f"risk_{r}", lang)))
    hedge = "" if points else t("hedge", lang)
    question = ""
    if mode in ("build_case", "explain") and not state.get("conflicts"):
        question = next_question(domain, state["facts"], lang) or ""
    lines = [p["text"] + "".join(f" [{r}]" for r in p["refs"]) for p in points]
    if hedge:
        lines.append(hedge)
    lines += notes
    if question:
        lines.append(f"{t('next_q_prefix', lang)} {question}")
    reply = "\n\n".join(lines)
    blocks = {"points": points, "hedge": hedge, "notes": notes, "question": question}
    return {
        "reply": reply,
        "blocks": blocks,
        "next_question": question,
        "citations": citation_meta([cards[i] for i in order], lang),
        "history": with_assistant(state, reply),
    }


async def canned(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    ctx = runtime.context
    lang, key = state["language"], state["canned"]
    if key == "needs_lawyer":
        what = ", ".join(t(f"risk_{r}", lang) for r in state["risks"] if r in LAWYER_RISKS)
        reply = t("needs_lawyer", lang, what=what)
    else:
        reply = t(key, lang)
    citations = []
    if key in ("needs_lawyer", "danger", "out_of_scope"):
        async with ctx.sessions() as session:
            citations = citation_meta([corpus.serialisable(c) for c in await corpus.get_cards(session, ["LSA-12"], ctx.today)], lang)
    return {
        "reply": reply,
        "blocks": {"canned": key, "text": reply},
        "citations": citations,
        "history": with_assistant(state, reply),
    }


async def practice(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    ctx = runtime.context
    domain, lang, message = state["domain"], state["language"], state["message"]
    who = OPPONENT[domain][lang]
    log = list(state.get("practice_log") or [])
    intro = t("practice_intro", lang, who=who) if not log else ""
    query = " ".join([message, *fact_values(state["facts"]).values()])
    async with ctx.sessions() as session:
        cards, _ = await corpus.retrieve(session, domain, query, ctx.today, embedder=ctx.embedder)
    cards = [corpus.serialisable(c) for c in cards]
    retrieved = {c["id"]: c for c in cards}
    system = PRACTICE.format(domain=domain, opponent=who, lang=LANG_NAME[lang])
    body = payload(
        facts=fact_values(state["facts"]), transcript=log[-6:], person_says=message, SOURCE_CARDS=cards_for_prompt(cards, lang)
    )
    them, tip, tip_sources = None, None, []
    for attempt in range(2):
        turn = await ctx.llm.structured("practice" if attempt == 0 else "practice_retry", PracticeTurn, system, body, ctx.recorder, key=message)
        if them is None and not roleplay_issues(turn.opponent_reply):
            them = turn.opponent_reply
        if tip is None:
            verdict = verify_points([{"text": turn.coach_tip, "sources": turn.sources}], retrieved, state["facts"])
            if verdict.kept:
                tip, tip_sources = verdict.kept[0]["text"], verdict.kept[0]["sources"]
        if them is not None and tip is not None:
            break
        problems = roleplay_issues(turn.opponent_reply) + [i for d in verify_points(
            [{"text": turn.coach_tip, "sources": turn.sources}], retrieved, state["facts"]).dropped for i in d["issues"]]
        system = system + "\n\n" + COMPOSE_RETRY.format(issues="\n".join(f"- {p}" for p in problems))
    them = them or t("practice_fallback_them", lang)
    tip = tip or t("practice_fallback_tip", lang)
    used = [retrieved[s] for s in tip_sources]
    refs = list(range(1, len(used) + 1))
    log.append({"you": message, "them": them})
    label_them = t("practice_label_them", lang, who=who)
    label_them = label_them[:1].upper() + label_them[1:]
    reply_parts = [intro] if intro else []
    reply_parts += [f"{label_them}: {them}", f"{t('practice_label_tip', lang)}: {tip}" + "".join(f" [{r}]" for r in refs)]
    reply = "\n\n".join(reply_parts)
    return {
        "practice_log": log[-20:],
        "reply": reply,
        "blocks": {"practice": {"intro": intro, "who": label_them, "them": them, "tip": tip, "refs": refs}},
        "citations": citation_meta(used, lang),
        "history": with_assistant(state, reply),
    }


async def notice(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    ctx = runtime.context
    lang, text = state["language"], state["message"]
    if len(text) < 60:
        reply = t("notice_need_text", lang)
        return {"reply": reply, "blocks": {"canned": "notice_need_text", "text": reply}, "history": with_assistant(state, reply)}
    reading = await ctx.llm.structured(
        "notice", NoticeReading, NOTICE.format(lang=LANG_NAME[lang]), payload(NOTICE_TEXT=text), ctx.recorder, key=text
    )
    deadline = norm(reading.deadline_quote) if reading.deadline_quote and grounded(reading.deadline_quote, reading.deadline_quote, text) else ""
    sender = norm(reading.sender) if reading.sender and grounded(reading.sender, reading.sender, text) else ""
    async with ctx.sessions() as session:
        cards = await corpus.get_cards(session, NOTICE_CARDS.get(reading.kind, []) + ["LSA-12"], ctx.today)
    cards = [corpus.serialisable(c) for c in cards]
    evidence = Evidence.build(cards, {"notice": {"value": text}})
    summary = [s for s in reading.summary if not problems_in(s, evidence, cited=True)]
    asks = reading.asks if not problems_in(reading.asks, evidence, cited=True) else ""
    kind_label = NOTICE_KINDS[reading.kind][lang]
    key = "summary_hi" if lang == "hi" else "summary_en"
    law_points = [{"text": c[key], "refs": [i + 1]} for i, c in enumerate(cards) if c["id"] != "LSA-12"]
    lawyer = t("notice_lawyer", lang, kind=kind_label) if reading.kind in SERIOUS_NOTICES else ""
    aid_ref = next((i + 1 for i, c in enumerate(cards) if c["id"] == "LSA-12"), None)
    deadline_line = t("notice_deadline", lang, quote=deadline) if deadline else t("notice_no_deadline", lang)
    lines = summary + ([asks] if asks else []) + [deadline_line]
    lines += [p["text"] + f" [{p['refs'][0]}]" for p in law_points]
    if lawyer:
        lines.append(lawyer + (f" [{aid_ref}]" if aid_ref else ""))
    reply = "\n\n".join(lines)
    notice_state = {"kind": reading.kind, "sender": sender, "deadline": deadline, "asks": asks, "excerpt": text[:400]}
    return {
        "notice": notice_state,
        "reply": reply,
        "blocks": {
            "notice": {
                "kind": kind_label, "sender": sender, "summary": summary, "asks": asks,
                "deadline": deadline, "deadline_line": deadline_line, "law": law_points, "lawyer": lawyer,
                "lawyer_ref": aid_ref,
            }
        },
        "citations": citation_meta(cards, lang),
        "history": with_assistant(state, reply),
    }


async def draft(state: CaseState, runtime: Runtime[Ctx]) -> dict:
    ctx = runtime.context
    domain, lang = state["domain"], state["language"]
    rows = [
        {"field": name, "label": spec(domain, name).label[lang], "value": state["facts"][name]["value"],
         "quote": state["facts"][name]["quote"]}
        for name in field_names(domain) if name in state["facts"]
    ]
    decision = interrupt({"kind": "confirm_facts", "domain": domain, "prompt": t("confirm_prompt", lang), "facts": rows})
    if not isinstance(decision, dict) or not decision.get("confirmed"):
        reply = t("draft_cancelled", lang)
        return {"reply": reply, "blocks": {"canned": "draft_cancelled", "text": reply}, "history": with_assistant(state, reply)}

    facts = {k: {**v, "confirmed": True} for k, v in state["facts"].items()}
    allowed = set(field_names(domain))
    for name, value in (decision.get("edits") or {}).items():
        value = norm(str(value))
        if name in allowed and 0 < len(value) <= 400:
            facts[name] = {"value": value, "quote": value, "turn": state["turn"], "confirmed": True, "edited": True}

    async with ctx.sessions() as session:
        cards = [corpus.serialisable(c) for c in await corpus.get_cards(session, DOCS[domain]["cards"], ctx.today)]

    dl = doc_lang(lang)
    system = DRAFT.format(doc_kind=DOCS[domain]["kind"][dl], party=DOCS[domain]["party"][dl], lang=LANG_NAME[dl])
    labelled = {spec(domain, k).label["en"]: v["value"] for k, v in facts.items() if spec(domain, k)}
    paragraphs, rejected = [], 0
    for attempt in range(2):
        narrative = await ctx.llm.structured(
            "draft" if attempt == 0 else "draft_retry", DraftNarrative, system, payload(facts=labelled), ctx.recorder, key=state["message"]
        )
        good = [p for p in narrative.paragraphs if p.strip() and not verify_plain(p, [], facts)]
        rejected += len(narrative.paragraphs) - len(good)
        if good:
            paragraphs = good
            break
    used_fallback = not paragraphs
    if used_fallback:
        paragraphs = fallback_paragraphs(domain, lang, facts)
    content = render(domain, lang, facts, paragraphs, cards)

    async with ctx.sessions() as session:
        doc = Document(case_id=uuid.UUID(state["case_id"]), kind=f"{domain}_letter", language=dl, content=content)
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    reply = t("draft_ready", lang)
    return {
        "facts": facts,
        "confirmed": True,
        "draft": {"id": doc_id, "kind": f"{domain}_letter", "used_fallback": used_fallback, "rejected_paragraphs": rejected},
        "reply": reply,
        "blocks": {"draft": {"id": doc_id, "text": reply, "preview": content, "rejected": rejected, "fallback": used_fallback}},
        "citations": citation_meta(cards, lang),
        "history": with_assistant(state, reply),
    }
