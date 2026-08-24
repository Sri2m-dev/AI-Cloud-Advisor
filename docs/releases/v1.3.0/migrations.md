# Migration History

The tagged repository and linked DEV Supabase migration ledger were compared on
2026-08-10. Every local version was present remotely and every remote version was present
locally. No migration was applied, repaired, or modified during P4.3.0 certification.

| Version | Migration |
| --- | --- |
| `202607230001` | `public_security_reconciliation` |
| `202607260001` | `aws_cur_ingestion_foundation` |
| `202607290001` | `enterprise_financial_data_fabric` |
| `202607290002` | `optimize_enterprise_financial_posture` |
| `202607290003` | `materialize_cloud_financial_projections` |
| `202607290004` | `correct_persisted_fact_posture` |
| `202607300001` | `bound_enterprise_financial_posture` |
| `202607310001` | `add_import_history_billing_period` |
| `202607310002` | `cloud_account_registry` |
| `202608080001` | `fg002_account_resolution` |
| `202608090001` | `p42_enterprise_classification` |
| `202608090002` | `p42_owner_optional_resolution` |
| `202608090003` | `p42_aws_user_tag_normalization` |
| `202608090004` | `p42_inference_persistence_rpc` |
| `202608090005` | `p42_persistence_lock_key` |
| `202608090006` | `p42_batch_account_evidence` |
| `202608090007` | `p42_single_scan_batch_evidence` |

`supabase migration list --linked` reported identical Local and Remote columns for all
17 versions. Local Docker-backed Supabase services were not running, which affected only
`supabase status`; the linked remote ledger query completed successfully.
