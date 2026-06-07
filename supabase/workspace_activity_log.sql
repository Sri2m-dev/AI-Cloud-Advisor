-- Workspace Activity Log Table for Auditability, Analytics, and Compliance
CREATE TABLE IF NOT EXISTS public.workspace_activity_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_email TEXT NOT NULL,
    role TEXT,
    workspace TEXT,
    action TEXT NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workspace_activity_log_user ON public.workspace_activity_log (user_email, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_activity_log_workspace ON public.workspace_activity_log (workspace, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_activity_log_action ON public.workspace_activity_log (action, created_at DESC);
