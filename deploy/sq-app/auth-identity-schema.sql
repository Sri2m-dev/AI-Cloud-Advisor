CREATE TABLE public.organizations (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    status text NOT NULL CHECK (status IN ('active', 'inactive'))
);

CREATE TABLE public.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    email text NOT NULL UNIQUE,
    org_id uuid NOT NULL REFERENCES public.organizations(id),
    role text NOT NULL CHECK (role IN ('viewer', 'auditor'))
);

CREATE INDEX users_org_id_idx ON public.users (org_id);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_select_self
ON public.users
FOR SELECT
TO authenticated
USING (auth_user_id = (SELECT auth.uid()));

CREATE POLICY organizations_select_own
ON public.organizations
FOR SELECT
TO authenticated
USING (
    id = (
        SELECT u.org_id
        FROM public.users AS u
        WHERE u.auth_user_id = (SELECT auth.uid())
        LIMIT 1
    )
);

GRANT USAGE ON SCHEMA public TO anon, authenticated, authenticator;
GRANT SELECT ON public.users, public.organizations TO authenticated;
GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated;

NOTIFY pgrst, 'reload schema';
