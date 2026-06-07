# Database Schema Inventory

| Table Name                  | Exists | Used By                | Status   | Notes |
|----------------------------|--------|------------------------|----------|-------|
| recommendations            | YES    | approval               | good     |       |
| recommendation_actions     | YES    | workflow               | good     |       |
| recommendation_events      | NO     | dashboard              | broken   |       |
| cost_data                  | NO     | cost_analysis          | broken   |       |
| ...                        | ...    | ...                    | ...      |       |

## Instructions
- Fill out this table for every table, view, or KPI in your platform.
- Mark Exists as YES/NO.
- List which module/page uses it.
- Status: good, broken, missing, legacy, etc.
- Add notes for migration, consolidation, or refactoring needs.
