"""Shared builders for the Phase-4 adapter-boundary battery. NOT a test module.

Everything here is deliberately boring and driven by the FROZEN contract, never by the
implementation: a scriptable adapter double whose call log is the negative oracle (a simulator
written from the implementation is the L-9 false-pass loophole), a mint-only helper that produces a
genuine grant+witness+handle for the boundary to claim, and the approved fingerprint read straight
off the grant row so the readback match is real.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon import effect_boundary as eb  # noqa: E402
from freight_recon.checkpoint import CheckpointAuthorized, run_checkpoint  # noqa: E402

# Reuse the P3 kit wholesale: same stores, same controllable clock, same green scenario.
from phase3_kit import (  # noqa: E402,F401
    EPOCH,
    T_A,
    T_B,
    Clock,
    checkpoint_and_claim,
    grant_rows,
    green_scenario,
    make_kernel,
    make_store,
    params_for,
    witness_rows,
)

OP_ID = "A4.create_invoice"


def approved_fingerprint(store, commit_key: str) -> str:
    rows = grant_rows(store, commit_key)
    assert rows, "no grant row minted — the mint helper was misused"
    return rows[0]["material_facts_fingerprint"]


class FakeTmsAdapter:
    """A scripted TMS write adapter (A4). It records EVERY call — the call log is the negative
    oracle for 'the world was touched exactly once' and 'the world was not touched at all'. It
    NEVER decides VERIFIED/FAILED: it returns structured evidence and lets the boundary decide.

    `mode`     : 'ok' | 'preflight_reject' | 'unknown' | 'raise_generic'
    `readback` : 'match' | 'conflict' | 'blind'
    """

    def __init__(self, *, approved: str, mode: str = "ok", readback: str = "match") -> None:
        self.approved = approved
        self.mode = mode
        self.readback_mode = readback
        self.calls: list[tuple[str, str]] = []

    def perform(self, cap: eb.ExecutionCapability, params) -> eb.AttemptResult:
        # The adapter's first line: prove the capability. A raw/forged call raises here.
        eb.consume_capability(cap, op_id=OP_ID)
        if self.mode == "preflight_reject":
            # Provable non-occurrence BEFORE any external attempt.
            raise eb.AdapterPreflightRejected(
                "TMS rejected pre-flight: invoice number already exists; no write issued")
        if self.mode == "unknown":
            # The call may have touched the world; the outcome is ambiguous.
            raise eb.AdapterOutcomeUnknown(
                "browser session dropped mid-submit", exposure="GBP 2,850.00")
        if self.mode == "raise_generic":
            # A generic, UNCLASSIFIED failure mid-attempt (a browser crash, a KeyError parsing the
            # response) — NOT a typed boundary exception. It carries no proof of non-occurrence and
            # no explicit UNKNOWN signal. The click already landed, so the world MAY be touched: the
            # call is logged before the raise to make that ambiguity real for the negative oracle.
            self.calls.append(("write", params.target_resource_id))
            raise RuntimeError("browser crashed after clicking submit; response never parsed")
        self.calls.append(("write", params.target_resource_id))
        return eb.AttemptResult(external_ref="INV-1001", detail="submitted")

    def readback(self, params) -> eb.ReadbackObservation:
        self.calls.append(("readback", params.target_resource_id))
        if self.readback_mode == "blind":
            return eb.ReadbackObservation(health_signal=False, observed_fingerprint=None,
                                          detail="logged-out page that loads fine")
        observed = self.approved if self.readback_mode == "match" else "CONFLICTING-FINGERPRINT"
        return eb.ReadbackObservation(health_signal=True, observed_fingerprint=observed)

    @property
    def writes(self) -> list[tuple[str, str]]:
        return [c for c in self.calls if c[0] == "write"]

    def operation(self) -> eb.AdapterOperation:
        return eb.AdapterOperation(
            op_id=OP_ID, adapter="A4",
            operation_class=eb.OperationClass.CONSEQUENTIAL_EFFECT,
            verification_mode=eb.VerificationMode.READBACK_VERIFIABLE,
            perform=self.perform, readback=self.readback)


def mint_only(tmp_path: Path, **kw):
    """Run the seven-step checkpoint and return the pieces the boundary needs, WITHOUT claiming.
    The boundary performs the claim itself (that is step 5 of the adapter algorithm)."""
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = green_scenario(
        tmp_path, **kw)
    outcome = run_checkpoint(kernel, request, inputs)
    assert isinstance(outcome, CheckpointAuthorized), "the green scenario failed to mint — kit misconfigured"
    fp = approved_fingerprint(store, effect.key())
    return store, kernel, clock, effect, outcome.handle, fp, request
