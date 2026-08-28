# PUE-ACT-002G in-page acceptance

ACT-C2 browser certification now uses the canonical `EvidencePilotAdmission`
held by the active Streamlit session. When and only when
`PUE_PILOT_DEV_MODE=true` and `ENVIRONMENT=development`, Analyze Environment
shows session-local Shadow, Evidence Discovery, Capabilities, and Kill Switch
controls after structural upload admission.

The controls do not construct or edit evidence scope. They pass the admitted
analysis scope to the existing ACT-C1 activation service, restrict selection to
Stages 0/1/2, and use the ACT-C1 kill-switch contract. Session state retains only
the selected presentation stage, kill-switch display state, and the admission
fingerprint that binds those preferences to the current upload.

The `.streamlit/pue-pilot-active-scope.json` and
`.streamlit/pue-pilot-dev.json` harness remains secondary development tooling
for existing tests and references. It is not required for ACT-C2 browser
certification and should be considered for removal in a later, separately
tested cleanup.

## Revised manual test

1. Start the app with `PUE_PILOT_DEV_MODE=true` and
   `ENVIRONMENT=development`.
2. Log in and upload `CUR Jan 2026.xlsx`.
3. Confirm the legacy unsupported-schema error can remain visible.
4. Select Evidence Discovery and verify row 5, 184 primary records, and
   observed fields are shown without semantic claims.
5. Select Capabilities and verify Total cost is BLOCKED with no PUE numeric
   total.
6. Select Kill Switch and verify PUE panels disappear while the legacy upload
   state remains.
7. Select Shadow and verify the same immediate rollback behavior.

No external control file, second terminal, active-scope lookup, or browser
refresh is part of this test.
