# Build Supervision Protocol

This protocol defines how Neyma should be built with two roles:

1. **Implementing Agent** — writes code, runs commands, builds features.
2. **Principal Architect Supervisor** — audits direction, production readiness, safety,
   design-partner fit, and real-product alignment.

The point is to avoid relying on repeated prompting. Future build sessions should start from
these repo docs and enforce this protocol automatically.

## Principal Architect Supervisor Role

The supervisor is the production-minded principal engineer and product architect for Neyma.

It should evaluate every meaningful change against:

- [Neyma Vision](NEYMA_VISION.md)
- [Agentic Architecture](AGENTIC_ARCHITECTURE.md)
- [Product Roadmap](PRODUCT_ROADMAP.md)
- [Design Partner Pilot Playbook](DESIGN_PARTNER_PILOT.md)
- [When Design Partner Data Arrives](WHEN_DESIGN_PARTNER_DATA_ARRIVES.md)
- `AGENTS.md`

The supervisor should be skeptical, practical, and freight-workflow aware. Its job is not to
make the builder feel good. Its job is to protect the path to a design-partner pilot and later
production.

## What The Supervisor Checks

### Product Alignment

- Does the change support Neyma as a freight-ops operational teammate?
- Does it keep the core experience in Slack/Teams/email/TMS/browser/API rather than forcing a
  new dashboard?
- Does it support the first teammate family: Document & Data Entry?
- Does it advance the first workflow: carrier invoice reconciliation?
- Does it avoid building broad platform features before design-partner proof?

### Architecture Alignment

- Is workflow control explicit through LangGraph or a state machine?
- Is LangChain/native tool calling used only where the LLM needs tools, retrieval, or drafting?
- Are Pydantic schemas used for typed contracts?
- Are money decisions deterministic Python?
- Are browser/API/TMS actions behind adapters?
- Does workflow state control tool access?
- Are high-risk tools gated by human approval?

### Design-Partner Readiness

- Can this run against the design partner's real documents/data?
- Does it support historical closed-load evaluation before live pilot?
- Does it avoid autonomous TMS write during the first pilot?
- Does the output make sense in Slack/Teams/email?
- Can human corrections become eval data?

### Production Safety

- Is idempotency content-hash based?
- Are retries safe?
- Are every state transition and tool call auditable?
- Are secrets and customer sessions handled safely?
- Are browser agents domain-limited, timeout-bounded, and readback-verified?
- Are failure states visible and safe?

### Evaluation

- Are there tests/evals for the changed behavior?
- Does the change preserve existing eval harness tests?
- If extraction changes, is there before/after eval evidence?
- If reconciliation changes, are fixture scenarios covered?
- If tool permissions change, are blocked-tool tests covered?

## Required Build Flow

For non-trivial implementation work:

1. Implementing Agent reads the relevant docs and code.
2. Implementing Agent states the concrete build target and gate.
3. Implementing Agent builds the smallest useful slice.
4. Implementing Agent runs tests/evals.
5. Principal Architect Supervisor reviews:
   - code
   - tests/evals
   - architecture fit
   - design-partner readiness
   - production safety
6. Implementing Agent fixes supervisor findings.
7. Supervisor gives final verdict.

## Supervisor Verdicts

Use these verdicts:

- **APPROVED** — production/design-partner direction is sound for this stage.
- **APPROVED WITH NITS** — safe to proceed, small cleanup remains.
- **CHANGES REQUESTED** — must fix before calling the slice done.
- **BLOCKED** — cannot proceed without partner data, secrets, environment access, or user input.

## Mandatory Evaluation Commands

Current baseline:

```bash
.venv/bin/python -m pytest eval/tests -q
.venv/bin/python scripts/run_extraction.py --render-only
.venv/bin/python eval/run_eval.py --mock eval/golden_set/mock_v1.json
.venv/bin/python eval/run_eval.py --mock eval/golden_set/mock_v2.json
```

When partner data arrives, add partner-specific eval commands and saved before/after reports.

## Access And Tooling Expectations

The implementing agent may use:

- Local filesystem and shell commands.
- Browser automation for local apps, mock TMS, and verification.
- Computer-use access when the task requires operating local desktop apps or inspecting the
  user's environment.
- Web search for current external docs, vendor behavior, or time-sensitive facts.

Access does not remove safety requirements. The supervisor should flag:

- Reading or committing sensitive partner data unnecessarily.
- Storing customer credentials.
- Browser automation without allowlists/timeouts.
- Any live write action without explicit approval and readback verification.

## Do Not Let The Build Drift Into

- A generic chatbot.
- A dashboard-first SaaS product.
- A free-roaming browser agent.
- LLM-driven money decisions.
- Premature TMS write automation.
- Overbuilt multi-workflow platform before the first design partner proves value.

## What Good Looks Like

For the first design partner, good looks like:

```text
real carrier invoice packet
→ structured extraction
→ deterministic reconciliation
→ state and audit event
→ Slack/Teams/email review message
→ human correction/approval captured
→ historical pilot metrics
```

Only after that should Neyma move toward live supervised operation, TMS read, and eventually
approved TMS write.
