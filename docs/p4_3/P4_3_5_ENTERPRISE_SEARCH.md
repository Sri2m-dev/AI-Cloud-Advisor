# P4.3.5 Enterprise Search

Enterprise Search is a deterministic, tenant-scoped read projection over the
P4.3.4 Intelligence service. It creates no index or source of truth. Contracts
are `SearchRequest`, `SearchResult`, and `SearchResponse`.

Ranking is stable: exact canonical ID (1000), authoritative source ID (950),
approved exact classification (925+confidence), canonical/display name (900),
alias (800), governed inferred value (650+confidence), then partial text. Extra
corroborating fields add a bounded tie-break score; canonical ID breaks ties.

Classification explanations retain approved versus inferred state and
confidence. Financial data is lazily requested from the Financial Data Fabric;
relationships expand only through governed edges. Evidence is limited to
administrators and auditors. Business and financial snippets are persona scoped.
Cross-tenant and mismatched authorization-scope requests fail before retrieval.

No cache is introduced. Pagination and a 100-result maximum bound retrieval.
Historical search is explicitly unsupported. Local runtime remains SQLite;
application runtime does not consume `P3_SUPABASE_TEST_*`, and Production remains
fail closed.

DEV release acceptance must verify `727482365532`, `HG_AWS01`, and `KordiaSoc`
against live governed data. Reference account spend is 37,143.2080151701 USD;
search never changes 786,745 CUR facts, total spend, or zero reconciliation.
Manual browser evidence remains required for overview, exact-account, account
name, inferred application, Needs Review, high-cost, and read-only persona views.
