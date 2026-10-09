-- Retire the legacy Auth trigger because it creates a duplicate profile by
-- Auth UUID and assigns every profile to a hard-coded organization. Controlled
-- production provisioning creates the organization and email-keyed profile
-- before inviting the Auth user, with independent profile/Auth UUIDs.
-- Keep the function for now; removing the trigger disables this incompatible
-- execution path without dropping the function or changing profile data.

begin;

drop trigger if exists on_auth_user_created on auth.users;

commit;
