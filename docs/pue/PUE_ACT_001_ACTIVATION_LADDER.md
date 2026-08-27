# PUE-ACT-001 Activation Ladder

| Stage | Name | Visible | Executable/routable |
|---:|---|---|---|
| 0 | `SHADOW_ONLY` | Nothing | Nothing; legacy remains authoritative |
| 1 | `EVIDENCE_DISCOVERY_VISIBLE` | Governed discovery, coverage, `UNKNOWN` and `NOT_EVIDENCED` | No calculated answer |
| 2 | `CAPABILITY_VISIBLE` | Stage 1 plus supported/blocked/unsupported capabilities and reasons | No PUE answer replacement |
| 3 | `SELECTED_ANSWERS` | Stage 2 plus explicitly approved certified answers | Selected answer visibility only; no automatic Ask routing |
| 4 | `ASK_NEXORA_SELECTED_ROUTING` | Stage 3 | Explicit allowlisted routing contract; not production-enabled by ACT-001 |
| 5 | `BROADER_AUTHORITY_REVIEW` | Definition only | Configuration forbidden in ACT-001 |

Feature flags are derived from the stage policy and never stored as scattered booleans. Confirmation UI remains false at every ACT-001 stage.

## 184-row behavior

- Stage 0: legacy path only; PUE remains shadow-blocked on currency.
- Stage 1: may expose 184 observed records, cost evidence, and missing governed currency. No PUE total.
- Stage 2: may expose `TOTAL_MEASURE → BLOCKED` with the currency reason.
- Stage 3: cannot surface a PUE numeric total because the governed chain produced none.
- Stage 4: routing follows the explicit fallback policy; PUE still cannot fabricate or blend `861828`.

## Promotion gates

Every promotion requires explicit administrative approval. Stage 0→1 requires discovery correctness acceptance; 1→2 requires coverage/capability UX acceptance; 2→3 requires persistence, confirmation, selected-answer, audit, and observability certification; 3→4 requires separate Ask Nexora routing acceptance. No health metric or successful run promotes a stage automatically.
