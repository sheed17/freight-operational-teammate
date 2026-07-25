# Adapter Family 03 — Sourcing & Carrier Outreach *(A5 Load Board · A6 Carrier Portal)*

*Registry + defaults apply.*

---
## A5 — Load Board Adapter
**Purpose.** Search/post/update/remove loads; ingest carrier responses + rate offers as **Observations/candidates**. **Not.** ### **A search result is EVIDENCE or a CANDIDATE — NEVER a confirmed Carrier Assignment.** **Vendors.** DAT, Truckstop — same contract. **Direction.** bidirectional.
| Op | class | verification | notes |
|---|---|---|---|
| A5-1 `search` / `read_market_rate` | ### **`DECISION_SUPPORT_READ`** | n/a | ### **market-rate evidence carries `as_of`+`stale`; freshness feeds a Quote's `expires_at` (a quote accepted after evidence expiry ⇒ re-price, H— #5)** |
| A5-2 `post_load` / `update` / `remove` | ### **`CONSEQUENTIAL_EFFECT`** (`POST_LOAD`) | ### **READBACK_VERIFIABLE** | posting verified by reading the board back; expiration is a durable timer |
| A5-3 `ingest_carrier_response` | `OBSERVATION_ONLY` | n/a | a response/rate offer is a Carrier Offer **candidate**; MC/DOT confirmed via A10, not the board display name |

**Identity.** ### **duplicate carrier identity across boards ⇒ confirmed on MC/DOT (A10), not the board alias (H12/H27).** **Counteroffers** ⇒ Offer versions. **Acceptance.** `test_a5_search_is_candidate_not_assignment`; `test_a5_market_rate_freshness_feeds_quote_expiry`. **Open.** board API tiers — NEEDS VALIDATION.

---
## A6 — Carrier Portal Adapter
**Purpose.** Read/write a carrier's portal (tender accept, docs, status). **Not.** authoritative for carrier qualification (that is A10 + the human-reserved decision). **Direction.** bidirectional (often browser-actuated via A15). **Ops.** `read_portal` (read class per caller); `submit_tender`/`upload_doc` (`CONSEQUENTIAL_EFFECT`, READBACK_VERIFIABLE). **Identity.** ### **the portal may display one MC but the carrier's email signature another (H12) ⇒ `ConflictRaised`/`AMBIGUOUS`, confirmed only on a trusted id.** **Security.** portal page content is untrusted (injection ⇒ signal). **Acceptance.** `test_a6_mc_mismatch_raises_conflict`. **Open.** per-portal automation posture.
