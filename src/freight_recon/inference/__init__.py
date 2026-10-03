"""The inference boundary: the ONE place new Neyma intelligence asks a model to read language.

    contracts.py         the Neyma task contracts: requests, typed outputs, the gateway Protocol
    prompts.py           what each task asks, and how a request is rendered
    gateway.py           the shared execution path: routing check, budget, bounded retry, validation
    ledger.py            token / call telemetry, the per-run budget, aggregation
    recording.py         record / replay of development evals
    scripted.py          the deterministic gateway every ordinary test uses
    openai_responses.py  the only production implementation, and the only importer of the OpenAI SDK
    settings.py          provider / model selection from the environment; pricing metadata

### A MODEL READS. IT DECIDES NOTHING. Every output here is an interpretation of text the caller
supplied: extracted facts with a verbatim evidence quote, candidate identifiers, commitments. None of
it is authority. The application decides what an interpretation may bear, deterministically, in
`freight_domain/interpretation.py`.

### THE APPLICATION DEPENDS ON THE CONTRACTS, NOT ON A PROVIDER. Nothing outside
`openai_responses.py` sees an OpenAI object. Importing this package imports no SDK and opens no
socket.
"""
