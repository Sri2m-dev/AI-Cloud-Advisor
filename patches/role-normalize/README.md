Role normalization patch bundle

This patch bundle contains updated page files and centralized role normalization helpers.

To apply manually:
- Copy files from `patches/role-normalize/` into the repository root, preserving paths.
- Run `streamlit run app_main.py` to validate behavior.

Notes:
- `auth/role_constants.py` contains `engineer -> technical` alias mapping.
- `scripts/smoke_role_routes.py` demonstrates normalization and routing mapping.
