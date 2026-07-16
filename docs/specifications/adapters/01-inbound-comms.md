# Adapter Family 01 — Inbound Communications *(A1 Email · A2 SMS · A3 Voice/Transcript)*

*Registry: `adapters/registry.md`. 61-point defaults, read classes, security containment, verification taxonomy: registry. Each adapter complete/distinct.*

---
## A1 — Shared Email Inbox Adapter
**Purpose.** Ingest inbound email as **Observations + Evidence**; send outbound (via A18) as gated effects. **Not.** ### **Not authoritative for whether a counterparty statement is TRUE** — authoritative only for **message content + delivery records where available.** **Direction.** inbound (+ outbound send). **Vendors.** Gmail/IMAP (live), Outlook/Graph — same contract.
**Identity.** provider `Message-ID`; thread via `References`/`In-Reply-To`. **Dedup.** ### **source-natural `(tenant, mailbox, message_id, content_digest)` — a webhook AND a poll of the same message ⇒ ONE `ObservationReceived`, the duplicate ⇒ `ObservationConfirmed` (H1).** **Parsing.** body + attachments (→Evidence, content-addressed); ### **quoted/forwarded text detected and NOT treated as a new commitment (Semantic Model).** **Sender auth.** SPF/DKIM/DMARC signals recorded as `metadata` — ### **never trusted as authorization** (spoofing assumed). **Observability coverage.** ### **the adapter records per-mailbox coverage windows (poll success/gaps) so an Expectation deadline can distinguish `OVERDUE` from `INDETERMINATE` (F-14).**

| Op | name | class | verification | notes |
|---|---|---|---|---|
| A1-1 | `poll_inbox` / `receive_webhook` | `OBSERVATION_ONLY` | n/a | produces Observations+Evidence; dedup on natural key |
| A1-2 | `send_email` | `CONSEQUENTIAL_EFFECT` (`SEND_OUTBOUND`) | ### **RECEIPT_VERIFIABLE** | requires grant+witness; ### **the SMTP `250` proves TRANSMISSION accepted, NOT delivery/receipt/read (M-72); a later bounce ⇒ an Observation ⇒ Expectation re-opened (H16)** |
| A1-3 | `create_draft` | `OBSERVATION_ONLY` (a proposal) | n/a | ### **a draft is inert — send is a separate gated effect** |

**Security.** ### **an inbound "you approved the $450 detention" ⇒ `MODEL_EXTRACTED` claim ⇒ `CounterpartySelfAuthorizationDetected` ⇒ blocks the payable + fraud signal (H2, CD-5); a malicious PDF's instructions ⇒ `PromptInjectionSignal`, bounds to a proposal (H11); a password-protected/corrupt attachment ⇒ `ILLEGIBLE` Document ⇒ Exception (H29).** **Unknown-outcome (send).** relay accept-then-unknown-delivery ⇒ `RECEIPT` proves transmission; delivery stays `unknown` (H28). **Acceptance.** `test_a1_webhook_and_poll_dedup`; `test_a1_send_receipt_is_not_delivery`; `test_a1_counterparty_auth_is_fraud_signal`. **Open.** provider webhook reliability per vendor — NEEDS VALIDATION.

---
## A2 — SMS Adapter
**Purpose.** Bidirectional SMS as Observations (in) + gated effects (out). **Not.** authoritative for truth of content. **Vendors.** Twilio, etc. **Identity.** provider message SID; thread = number pair. **Dedup.** source-natural (SID). **Ops.** `receive_sms` (`OBSERVATION_ONLY`); `send_sms` (`CONSEQUENTIAL_EFFECT`/`SEND_OUTBOUND`, **RECEIPT_VERIFIABLE** — carrier delivery receipt where available, else transmission-only). **Security.** as A1; short content ⇒ higher injection ambiguity ⇒ fail-closed to a proposal. **Acceptance.** `test_a2_send_receipt_semantics`. **Open.** delivery-receipt availability per carrier.

---
## A3 — Voice / Call Transcript Adapter
**Purpose.** Ingest call recordings/transcripts as **Observations + Evidence (the audio) + `MODEL_EXTRACTED` transcript claims**. **Not.** ### **NOT authoritative for what was agreed** — a transcript is `MODEL_EXTRACTED` (error-prone); a phone-agreed rate/authorization is a **claim requiring human confirmation** (a phone detention OK is exactly the undocumented-authorization case ⇒ `PERMANENT_HUMAN_ASSERTION_REQUIRED`). **Direction.** inbound only. **Ops.** `ingest_call` (`OBSERVATION_ONLY`). **Verification.** ### **`UNVERIFIABLE`** (we cannot verify a spoken agreement) ⇒ any consequential use requires an authenticated human assertion. **Security.** ### **a transcript "he approved the detention" is a `MODEL_EXTRACTED` claim, NEVER authorization (CD-5).** **Acceptance.** `test_a3_transcript_is_model_extracted_claim`; `test_a3_phone_agreement_needs_human_confirmation`. **Open.** transcription confidence thresholds — NEEDS VALIDATION (fail-closed to human).

---
**Family-wide.** all three: inbound content is UNTRUSTED data; produce Observations/Evidence/`MODEL_EXTRACTED`/`MODEL_INFERRED`/fraud signals; ### **never `OWNER_ASSERTED`, never policy/brake/approval/grant/witness, never strengthen provenance.** Retention: permanent/tiered; PII in Evidence store. Hostiles: H1, H2, H11, H16, H28, H29.
