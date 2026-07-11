# Data Fabric Migrations

This directory contains reviewed SQL migration files for the P3 Data Fabric Supabase PostgreSQL adapter foundation.

P3.13 adds migration files only. They are not executed automatically by application startup.

Safety rules:

- no destructive statements
- no production credentials
- no automatic runtime execution
- apply only through approved migration tooling
- test in isolated Supabase/PostgreSQL environment before production
