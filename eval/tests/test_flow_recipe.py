"""Tests for crystallize -> replay: learn a flow once, replay it deterministically."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.flow_recipe import (  # noqa: E402
    FlowRecipe,
    crystallize,
    load_recipe,
    recipe_to_plan,
    save_recipe,
    seed_context,
)
from freight_recon.operator_brain import FlowExecutor, FlowPlan, FlowStep, StepAction, StepResult, build_tool_handlers  # noqa: E402
from freight_recon.screen_discovery import DiscoveredInvoiceForm  # noqa: E402


def _form():
    return DiscoveredInvoiceForm(
        url="https://t.test/orders/new", submit_label="Save",
        bill_to_selector="[name=cust]", amount_selector="[name=amt]",
        invoice_number_selector="[name=num]", description_selector="[name=desc]",
    )


def _completed_plan():
    return FlowPlan(goal="invoice", steps=[
        FlowStep(StepAction.NAVIGATE, "https://t.test/orders/new"),
        FlowStep(StepAction.DISCOVER_FORM, "https://t.test/orders/new"),
        FlowStep(StepAction.RESOLVE_CUSTOMER, "Acme Brokerage"),
        FlowStep(StepAction.FILL_AND_SUBMIT, "https://t.test/orders/new"),
        FlowStep(StepAction.READBACK_VERIFY),
    ])


def test_crystallize_drops_discovery_and_bakes_form():
    recipe = crystallize(_completed_plan(), tms_host="t.test", goal_kind="customer_invoice", form=_form())
    actions = [s["action"] for s in recipe.steps]
    assert "DISCOVER_FORM" not in actions          # discovery is baked into form, not re-run
    assert "NAVIGATE" in actions and "FILL_AND_SUBMIT" in actions
    assert recipe.form["amount_selector"] == "[name=amt]"


def test_recipe_round_trips_through_disk(tmp_path):
    recipe = crystallize(_completed_plan(), tms_host="t.test", goal_kind="customer_invoice", form=_form())
    save_recipe(recipe, tmp_path)
    loaded = load_recipe(tmp_path, "t.test", "customer_invoice")
    assert isinstance(loaded, FlowRecipe)
    assert loaded.form["bill_to_selector"] == "[name=cust]"
    assert [s["action"] for s in loaded.steps] == [s["action"] for s in recipe.steps]
    assert load_recipe(tmp_path, "t.test", "nonexistent") is None


def test_replay_runs_deterministically_without_an_llm():
    recipe = crystallize(_completed_plan(), tms_host="t.test", goal_kind="customer_invoice", form=_form())
    plan = recipe_to_plan(recipe)
    ctx = seed_context(recipe)
    assert ctx["form"].amount_selector == "[name=amt]"  # form pre-seeded -> no discovery needed

    # A completer that MUST NOT be called during replay (deterministic).
    def no_llm(_prompt):
        raise AssertionError("replay must not call the model")

    class Sess:
        def __init__(self): self.nav = []
        def navigate(self, u): self.nav.append(u)
        def evaluate(self, e): return {}

    submitted = {}
    def gated_submit(c):
        submitted["form"] = c.get("form"); submitted["cid"] = c.get("customer_id")
        return StepResult(FlowStep(StepAction.FILL_AND_SUBMIT), ok=True, detail="gated write verified")

    handlers = build_tool_handlers(
        session=Sess(), complete=no_llm, resolve_customer=lambda n: "C9", gated_submit=gated_submit,
    )
    res = FlowExecutor(handlers=handlers).run(plan, ctx)
    assert res.completed
    # The baked form + freshly-resolved customer reached the gated write — no model call occurred.
    assert submitted["cid"] == "C9" and submitted["form"].amount_selector == "[name=amt]"
