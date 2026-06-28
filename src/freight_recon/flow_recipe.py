"""Crystallize a Brain-discovered flow into a deterministic recipe, and replay it without the LLM.

This is what makes the Operator Brain viable in production: the Brain reasons a multi-step flow ONCE
(expensive, non-deterministic), we crystallize the *path it found* + the *form selectors it mapped*
into a :class:`FlowRecipe`, and every subsequent run REPLAYS that recipe deterministically — no model
call. The Brain is re-engaged only on novelty/failure (the caller falls back to ``plan_flow`` / re-plan).

What's baked into a recipe: the navigation path and the discovered field selectors (stable per TMS+goal).
What stays fresh per run: the customer (resolved each time) and the money (bound from the approval) —
never baked, so a recipe can't carry a stale amount or bill-to.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from freight_recon.operator_brain import FlowPlan, FlowStep, StepAction
from freight_recon.screen_discovery import DiscoveredInvoiceForm


@dataclass
class FlowRecipe:
    tms_host: str
    goal_kind: str                 # e.g. "customer_invoice" / "carrier_payable"
    steps: list[dict]              # ordered [{action, target, params}] — the learned path
    form: dict | None = None       # the discovered selector map (DiscoveredInvoiceForm fields)
    source: str = "brain"          # "brain" | "repaired"
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


_FORM_KEYS = (
    "url", "submit_label", "bill_to_selector", "amount_selector",
    "invoice_number_selector", "description_selector", "date_selector",
)


def _form_to_dict(form: DiscoveredInvoiceForm) -> dict:
    return {k: getattr(form, k) for k in _FORM_KEYS}


def _form_from_dict(data: dict) -> DiscoveredInvoiceForm:
    return DiscoveredInvoiceForm(**{k: data.get(k) for k in _FORM_KEYS})


def crystallize(plan: FlowPlan, *, tms_host: str, goal_kind: str, form: DiscoveredInvoiceForm | None = None,
                source: str = "brain") -> FlowRecipe:
    """Capture a *completed* plan's path + the discovered form into a replayable recipe.

    DISCOVER_FORM steps are dropped from the baked path (the selectors are stored once in ``form``), so
    replay needs no model call to re-map the screen.
    """
    steps = [
        {"action": s.action.value, "target": s.target, "params": dict(s.params)}
        for s in plan.steps
        if s.action != StepAction.DISCOVER_FORM
    ]
    return FlowRecipe(
        tms_host=tms_host, goal_kind=goal_kind, steps=steps,
        form=_form_to_dict(form) if form is not None else None, source=source,
    )


def recipe_to_plan(recipe: FlowRecipe) -> FlowPlan:
    """Rebuild a deterministic plan from a recipe (no LLM)."""
    steps = [
        FlowStep(action=StepAction(s["action"]), target=s.get("target", ""), params=s.get("params", {}) or {})
        for s in recipe.steps
        if s.get("action") in StepAction._value2member_map_
    ]
    return FlowPlan(goal=f"{recipe.goal_kind} on {recipe.tms_host} (replay)", steps=steps,
                    notes=[f"replayed from {recipe.source} recipe @ {recipe.created_at}"])


def seed_context(recipe: FlowRecipe) -> dict:
    """Pre-seed the executor context with the recipe's discovered form, so replay skips discovery."""
    ctx: dict = {}
    if recipe.form is not None:
        ctx["form"] = _form_from_dict(recipe.form)
    return ctx


def recipe_path(directory: str | Path, tms_host: str, goal_kind: str) -> Path:
    safe = f"{tms_host}__{goal_kind}".replace("/", "_").replace(":", "_")
    return Path(directory) / f"{safe}.json"


def save_recipe(recipe: FlowRecipe, directory: str | Path) -> Path:
    path = recipe_path(directory, recipe.tms_host, recipe.goal_kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(recipe.to_json(), encoding="utf-8")
    return path


def load_recipe(directory: str | Path, tms_host: str, goal_kind: str) -> FlowRecipe | None:
    path = recipe_path(directory, tms_host, goal_kind)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return FlowRecipe(**data)
