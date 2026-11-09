from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from . import nodes
from .state import CaseState, Ctx


def build_graph(checkpointer=None):
    g = StateGraph(CaseState, context_schema=Ctx)
    for name in ("ingest", "guard", "extract", "retrieve", "compose", "verify", "respond", "canned", "practice", "notice", "draft"):
        g.add_node(name, getattr(nodes, name))
    g.add_edge(START, "ingest")
    g.add_edge("ingest", "guard")
    g.add_conditional_edges("guard", nodes.after_guard, ["canned", "notice", "practice", "extract"])
    g.add_conditional_edges("extract", nodes.after_extract, ["draft", "retrieve"])
    g.add_edge("retrieve", "compose")
    g.add_edge("compose", "verify")
    g.add_conditional_edges("verify", nodes.after_verify, ["compose", "respond"])
    for terminal in ("respond", "canned", "practice", "notice", "draft"):
        g.add_edge(terminal, END)
    return g.compile(checkpointer=checkpointer)


@dataclass
class TurnResult:
    state: dict
    pending: Any


def config_for(case_id: str) -> dict:
    return {"configurable": {"thread_id": case_id}}


async def pending_interrupt(graph, case_id: str):
    snapshot = await graph.aget_state(config_for(case_id))
    interrupts = getattr(snapshot, "interrupts", ()) or ()
    return interrupts[0].value if interrupts else None


async def run_turn(graph, ctx: Ctx, case_id: str, message: str, mode: str = "auto", language: str = "auto") -> TurnResult:
    cfg = config_for(case_id)
    if await pending_interrupt(graph, case_id) is not None:
        await graph.ainvoke(Command(resume={"confirmed": False}), cfg, context=ctx)
    state = await graph.ainvoke(
        {"case_id": case_id, "message": message, "requested_mode": mode, "language_pref": language}, cfg, context=ctx
    )
    return TurnResult(state=state, pending=await pending_interrupt(graph, case_id))


async def resume(graph, ctx: Ctx, case_id: str, decision: dict) -> TurnResult:
    cfg = config_for(case_id)
    state = await graph.ainvoke(Command(resume=decision), cfg, context=ctx)
    return TurnResult(state=state, pending=await pending_interrupt(graph, case_id))


async def current_state(graph, case_id: str) -> dict:
    snapshot = await graph.aget_state(config_for(case_id))
    return dict(snapshot.values or {})
