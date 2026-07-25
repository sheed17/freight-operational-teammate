# Adapter Family 09 — Human Oversight Surface Adapter *(A14)*

*Registry: `adapters/registry.md`. Vendor-neutral (Slack live; CLI/web/email fallbacks — same contract).*

**Purpose.** ### **TRANSPORT a human decision — render a decision packet, receive an approval/rejection/correction/brake action — and carry it to the machines.** **Not.** ### **NOT a decision-maker — it may TRANSPORT a human decision; it may NEVER INVENT one.** Not authoritative for any domain fact. **Direction.** bidirectional (render out, decision in).

## Decision packet & immutable action identity
- **Renders:** the Approval card (the exact Material Facts — amount as integer minor units, party, load, bound document digests, provenance, `as_of`), the drift explanation, the brake report, exception/escalation queues.
- ### **Immutable action identity:** every rendered actionable option (an Approve button, an "assign unlinked N" option) carries a **single-use HMAC token bound to `(action_id, tenant, channel, thread, user)`** AND ### **resolves at DISPLAY time to an IMMUTABLE artifact/Work-Item id — NEVER a mutable-list ordinal (L-B).**
- ### **Ordinal risk (H21):** "unlinked item 2" is resolved to the `observation_id` shown at render; if the list changed, the action binds to the **originally-displayed id, or FAILS CLOSED** — never to the new occupant of slot 2.

## Operations *(the adapter TRANSPORTS; the machines decide)*
| Op | name | class | notes |
|---|---|---|---|
| A14-1 | `render_packet` | `OBSERVATION_ONLY` (outbound render) | ### **RECEIPT_VERIFIABLE for the render itself; the render is not an effect** |
| A14-2 | `receive_approval` | transports `HumanApproved` → M4 | ### **`actor_type=human`, authenticated; a stale/replayed click ⇒ the CAS/drift check decides (H20 — drift ⇒ `VOID_ON_DRIFT`, the button click cannot force it); a double-tap ⇒ idempotent "already done"** |
| A14-3 | `receive_rejection`/`correction` | transports `HumanDenied`/`HumanCorrected{decision_ref}` | correction carries a resolvable `decision_ref` |
| A14-4 | `engage_brake` | transports `BrakeEngaged` (BR-1) | ### **any authenticated operator; instant; works when the system is unhealthy** |
| A14-5 | `release_brake` | transports `BrakeReleased` (BR-4) | ### **authenticated human ONLY + the release evidence; the adapter cannot release on its own (H — automation/model never releases)** |
| A14-6 | `assign_owner`/`escalate` | native updates | — |

## Security
### **The oversight surface is INSIDE the trust boundary for AUTHENTICATED humans (their action is `OWNER_ASSERTED`) — but a message IN a Slack channel from an unauthenticated party is still untrusted content. A model posting to the channel is `actor_type=model` and can NEVER produce an approval/brake-release.** Duplicate interaction ⇒ idempotent; stale interaction (drift/brake moved) ⇒ the machine's guard decides, not the button.

**Acceptance.** `test_a14_transports_never_invents_a_decision`; `test_a14_ordinal_resolves_to_immutable_id_or_fails_closed` (H21); `test_a14_stale_button_after_drift_voids` (H20); `test_a14_double_tap_idempotent`; `test_a14_only_human_releases_brake`. **Adversarial.** H20, H21. **Open.** channel strategy per tenant; MFA on high-value approvals — NEEDS VALIDATION.
