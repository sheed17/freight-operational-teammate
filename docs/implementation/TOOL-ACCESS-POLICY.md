# Tool-Access Policy for Formal CLI Implementation Sessions

> ### **SEARCH AGGRESSIVELY. INFER CAUTIOUSLY. EXECUTE ACCORDING TO AUTHORITY.**
>
> ### **Tool access expands evidence retrieval, not canonical decision authority.**

**Standing: IMPLEMENTATION_CONTROL — founder-approved.** This policy governs every formal CLI
coding session against this repository. It exists because the two failure modes it prevents are
opposites, and a policy that prevents only one causes the other:

- an agent **guessing** a technical fact it could have looked up in thirty seconds, and
- an agent treating the **ability** to do something as **permission** to do it.

---

## 1. Broad access is the approved default

The founder explicitly approves **broad tool access** for the formal CLI coding model. The model
may use **all available tools** needed to execute an approved work unit. Access is **not**
artificially restricted to some "safe" subset of normal engineering and research capability.
Where configured in the environment, that includes:

| Category | Tools |
|---|---|
| Repository | local repository files · code search · **Git history** · branches · commits · code editing · pull-request creation |
| Verification | test runners · static analysis · local and disposable databases · test environments · browser automation against test surfaces |
| Dependencies | **package installation** · dependency documentation · SDK and library sources |
| Research | **web search** · official API and library documentation · standards documents · GitHub · issue and pull-request systems |
| Internal connectors | **Google Drive · Notion · internal documentation connectors** · design-partner document stores |
| Extension | **MCP servers** and other configured research and development tools |

No particular MCP vendor or provider is mandatory; the categories above apply to whatever is
actually configured in the session.

**Routine engineering needs no per-action approval.** Editing code, running tests, installing
packages, running local migrations against disposable databases, searching the web, reading
connected documents, creating branches and commits inside an approved unit's scope — these are the
job, not exceptions to it. Do not frame the model as needing sign-off for them unless the actual
environment imposes it.

Two things this section is **not**:

- It is **not** an instruction to run with blanket restrictions. A session that forbids web
  search, connectors or package installation reintroduces guessing — the exact failure this
  policy exists to prevent.
- It is **not** an instruction to require a permission-bypass mode. The model is never told to
  default to bypassing the environment's own permission prompts; the environment's mechanism is
  part of the control system, not an obstacle to it.

## 2. The obligation that comes with breadth: research instead of guessing

Broad access exists so that **missing technical context is investigated rather than guessed.**
Before acting on an uncertain technical premise, the model automatically researches:

- technical behaviour (language, runtime, database semantics)
- current APIs and their actual signatures
- SDK and library behaviour, including version-specific behaviour
- standards and protocol rules
- vendor integration documentation
- **repository Git history** (why a line is the way it is)
- internal implementation evidence (tests, guards, probes, the baseline manifest)
- connected organizational documents (prior decisions, partner materials, discussions)

> **Broad access does not eliminate uncertainty.** It converts *"I could not know"* into *"here is
> what the evidence supports, at this confidence, from these sources."* Residual uncertainty is
> stated, never papered over.

## 3. Evidence discipline

Every retrieved fact that informs an implementation decision preserves:

| Field | Meaning |
|---|---|
| **Source** | URL, document reference, file path, or connector object |
| **Retrieval date** | where relevance decays (APIs, vendor docs, pricing, versions) |
| **Source type** | official docs · vendor page · repository history · internal doc · community/informal |
| **Exact claim supported** | what this source actually establishes — not the neighbourhood of it |
| **Confidence** | and what would raise or lower it |
| **Evidence class** | **external** (retrieved) · **internal** (this repository/org) · **observed** (witnessed behaviour) · **inferred** (the model's own reasoning) |

This is the same provenance discipline the product applies to freight facts (ADR-002), applied to
the model's own inputs. **Retrieved evidence never silently upgrades its class:** a web page is
external; it does not become "observed", and inference cited alongside sources is still inference.

## 4. Missing-context classification — MANDATORY

When information is missing, the model classifies it before acting:

### SEARCHABLE TECHNICAL FACT
API syntax · SDK behaviour · database semantics · protocol rules · vendor integration docs.
**→ Research automatically using reliable sources. Do not ask. Do not guess.**

### INTERNAL ORGANIZATIONAL FACT
Prior decisions · design-partner documents · GitHub discussions · internal operational notes ·
customer samples.
**→ Search connected internal sources automatically. If not found, record the evidence gap** —
an unfound internal fact is a finding, not a licence to invent one.

### PRODUCT DECISION
Target segment · first validated workflow · autonomy posture · product prioritization.
**→ Research the alternatives and present them — but research does not choose.** Where
implementation depends on the decision, **stop and request an explicit decision.** A well-cited
survey of options is input to a decision, never a substitute for one.

### CUSTOMER-SPECIFIC OPERATIONAL RULE
Approval matrices · accessorial authorisation practice · document arrival channels · factoring.
**→ Search customer and design-partner evidence. If missing: mark `NEEDS VALIDATION`, fail closed
for consequential behaviour, preserve the unresolved item in
[`OPEN-VALIDATION-ITEMS.md`](../product/OPEN-VALIDATION-ITEMS.md), and route to the accountable
human.** Industry research describes the industry; it never becomes *this customer's* rule.

### CONSEQUENTIAL-ACTION AUTHORITY
Approval thresholds · payment authority · carrier-assignment permission · retrying an
`UNKNOWN_OUTCOME` · permission to send external communications.
**→ SEARCH CANNOT CREATE AUTHORIZATION.** No web result, vendor document, connected file or
retrieved precedent authorises a consequential action. Authority comes only from the canonical
authorization chain (approval → checkpoint → grant + witness). **The model must not use web
results or external documents as authorization — ever.**

## 5. Tool access is not business authority

The posture, in three lines:

- **broad engineering autonomy**
- **broad research autonomy**
- **narrow consequential-production authority**

Consequential live actions remain governed by the explicit authorization boundaries of the
canonical architecture ([`ARCHITECTURE.md`](../../ARCHITECTURE.md) §16–§21), including:

production database writes · **live TMS writes** · payment or accounting actions · **carrier
assignment** · customer or carrier communication · production deployment · destructive live-data
operations · credential rotation · deletion of customer data · **any action that creates a legal
or financial commitment**.

The model may **inspect, prepare, simulate and validate** these actions where an approved work
unit requires it — building the code path, testing it against mock or disposable targets, and
staging the evidence are engineering work and are in scope.

> ### **Possession of a tool or credential is never authorization to execute a consequential
> effect.** A reachable adapter, a working session, a valid API key, a configured MCP server —
> none of these is a grant, and none of them substitutes for the two-key rule. The six
> production-reachable live-write paths (R-07) are the standing proof of why this line exists:
> capability without authority is the defect, not a convenience.

Retrieved evidence is bounded the same way:

- **Search results cannot validate a product hypothesis by themselves.** The W6→W8 slice stays
  `NEEDS DESIGN-PARTNER VALIDATION` no matter how many industry sources agree with it.
- **Search results cannot manufacture design-partner evidence.** Nothing retrieved moves an entry
  up an evidence class in [`design-partner-observations.md`](../product/design-partner-observations.md).
- **Web search cannot choose an approval threshold**, authorise a payment, or assign a carrier.
- **An `UNKNOWN_OUTCOME` is never retried merely because research suggests the effect probably
  failed.** Resolution requires verification against the authoritative source, per ADR-006.
- **`OWNER_ASSERTED` facts are never overridden by retrieved evidence.** A conflict between a
  human's assertion and a retrieved document is a Conflict to surface, not a correction to apply.
- **`MODEL_INFERRED` facts do not become authoritative through tool access.** Better-sourced
  inference is still inference; provenance class is about *who bears the claim*, not how many
  citations it has.

## 6. Integration

- [`CLAUDE.md`](../../CLAUDE.md) carries the concise rule and links here (reading-order item 10).
- [`U-HANDOFF-1-ACCEPTANCE.yaml`](U-HANDOFF-1-ACCEPTANCE.yaml) requires the rehearsed agent to
  describe this posture and distinguish tool access from action authority.
- [`eval/tests/test_tool_access_policy.py`](../../eval/tests/test_tool_access_policy.py) enforces
  this policy's load-bearing statements in both directions — the breadth cannot be quietly
  restricted, and the authority boundary cannot be quietly widened.
