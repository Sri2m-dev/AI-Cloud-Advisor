# Schema Governance Standards

## Standards
- Use `snake_case` for all table and column names
- Use `*_id` for all identifier columns
- Use `*_at` for all timestamp columns
- Use `*_status` for all state columns

## Naming Rules
- organization_id
- approval_status
- created_at
- updated_at
- assigned_to_user_id

## Mandatory Metadata
Every table must include the following columns:
- `id` (primary key)
- `org_id` (organization identifier)
- `created_at` (timestamp of creation)
- `updated_at` (timestamp of last update)
- `created_by` (user who created the record)
- `updated_by` (user who last updated the record)

## Example Table Definition
```sql
CREATE TABLE example_table (
    id SERIAL PRIMARY KEY,
    org_id INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by INTEGER NOT NULL,
    updated_by INTEGER NOT NULL,
    approval_status VARCHAR(32),
    assigned_to_user_id INTEGER
);
```

## Additional Notes
- All foreign keys should reference the appropriate `*_id` column.
- Avoid abbreviations unless industry standard.
- All timestamps should be in UTC.
- Document any exceptions to these rules in this file.
