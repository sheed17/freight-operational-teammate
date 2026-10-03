"""A small vocabulary for authoring typed model READINGS by hand.

The corpus needs to say what a careful reader would report for a piece of freight language — as the
labeled answer an eval is scored against, and as the reply a scripted gateway hands back in tests.
These helpers only shorten writing a `MessageInterpretation` / `CandidateProposal` as plain data. They
add no behaviour: every dict they build is validated against the real contract when it is used.

SYNTHETIC. Every sentence quoted here is invented development input.
"""

from __future__ import annotations

from typing import Any


def message(*, category: str = "OTHER", response_requested: bool = False,
            **lists: list[dict[str, Any]]) -> dict[str, Any]:
    """A full message reading. Any list not given is empty."""
    names = ("statuses", "commitments", "appointments", "accessorials", "rates", "delays",
             "documents", "references", "corrections")
    unknown = set(lists) - set(names)
    if unknown:
        raise ValueError(f"not a message-reading list: {sorted(unknown)}")
    return {"category": category, "response_requested": response_requested,
            **{name: list(lists.get(name, ())) for name in names}}


def status(value: str, stop: str, evidence: str, *, quoted: bool = False) -> dict[str, Any]:
    return {"status": value, "stop": stop, "in_quoted_text": quoted, "evidence_text": evidence}


def promise(evidence: str, *, minutes: int | None = None, clock: str | None = None,
            day: int | None = None, text: str | None = None, action: str = "STATUS_UPDATE",
            actor: str = "SENDER", quoted: bool = False) -> dict[str, Any]:
    kind = "RELATIVE_MINUTES" if minutes is not None else "CLOCK_TIME" if clock else "NONE"
    return {"actor": actor, "promised_action": action, "time_kind": kind,
            "relative_minutes": minutes, "clock_time_24h": clock,
            "day_offset": (day if day is not None else 0) if clock else None,
            "time_text": text, "in_quoted_text": quoted, "evidence_text": evidence}


def appointment(stop: str, evidence: str, *, day: int | None, start: str | None,
                end: str | None = None, state: str = "CONFIRMED",
                quoted: bool = False) -> dict[str, Any]:
    return {"stop": stop, "appointment_status": state, "day_offset": day,
            "start_time_24h": start, "end_time_24h": end, "in_quoted_text": quoted,
            "evidence_text": evidence}


def charge(kind: str, evidence: str, *, amount: str | None = None, approved: bool = False,
           approver: str | None = None, label: str | None = None, currency: str | None = None,
           quoted: bool = False) -> dict[str, Any]:
    return {"charge_type": kind, "charge_label": label or kind.lower(), "amount_text": amount,
            "currency_code": currency, "asserts_prior_approval": approved,
            "approver_named": approver, "in_quoted_text": quoted, "evidence_text": evidence}


def rate(amount: str, evidence: str, *, quoted: bool = False) -> dict[str, Any]:
    return {"amount_text": amount, "currency_code": None, "in_quoted_text": quoted,
            "evidence_text": evidence}


def delay(evidence: str, *, reason: str | None = None, stop: str = "UNSPECIFIED",
          quoted: bool = False) -> dict[str, Any]:
    return {"stop": stop, "reason_text": reason, "in_quoted_text": quoted,
            "evidence_text": evidence}


def paper(doc_type: str, presence: str, evidence: str, *, quoted: bool = False) -> dict[str, Any]:
    return {"doc_type": doc_type, "presence": presence, "in_quoted_text": quoted,
            "evidence_text": evidence}


def reference(kind: str, value: str, evidence: str, *, role: str = "SUBJECT",
              quoted: bool = False) -> dict[str, Any]:
    return {"kind": kind, "value": value, "role": role, "in_quoted_text": quoted,
            "evidence_text": evidence}


def correction(kind: str, evidence: str) -> dict[str, Any]:
    return {"corrects": kind, "evidence_text": evidence}


def candidates(*picked: tuple[str, str, str]) -> dict[str, Any]:
    """`(candidate_id, support, evidence)` per proposed candidate."""
    return {"candidates": [{"candidate_id": cid, "support": support, "evidence_text": evidence,
                            "reason": "scripted"} for cid, support, evidence in picked]}


def pick(*needles: str, support: str = "CLEAR", evidence: str | None = None) -> Any:
    """A candidate responder: propose every SUPPLIED option whose summary contains a needle. It can
    only ever return ids it was handed — which is what a well-behaved reader does."""

    def respond(request: Any) -> dict[str, Any]:
        quote = evidence or request.text.strip().splitlines()[-1][:60]
        return candidates(*[(o.candidate_id, support, quote) for o in request.options
                            if any(needle in o.summary for needle in needles)])
    return respond
