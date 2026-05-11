-- Catalog collapse migration. Adds:
--   - users.pre_proposal_credits, users.full_proposal_credits (credit balances)
--   - proposals.payment_model: 'upfront' | 'success_fee' | NULL (legacy)
--   - pending_approvals: queue for Option B success-fee Full Proposal applications
--
-- PREREQUISITE (Supabase dashboard, one-time):
--   Create a private storage bucket named 'invitation-letters' before this
--   migration runs in the app. The migration itself does not touch storage.
--
-- Apply once against the Supabase project (SQL Editor or psql).

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS pre_proposal_credits  integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS full_proposal_credits integer NOT NULL DEFAULT 0;

ALTER TABLE proposals
    ADD COLUMN IF NOT EXISTS payment_model text;

CREATE TABLE IF NOT EXISTS pending_approvals (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid REFERENCES users(id) ON DELETE SET NULL,
    contact_email   text NOT NULL,
    product         text NOT NULL,                         -- e.g. 'full_proposal_success_fee'
    invitation_letter_path text NOT NULL,                  -- Supabase Storage object path inside the 'invitation-letters' bucket
    invitation_letter_name text,                           -- original client filename
    status          text NOT NULL DEFAULT 'pending',       -- 'pending' | 'approved' | 'rejected'
    requested_at    timestamptz NOT NULL DEFAULT now(),
    decided_at      timestamptz,
    decided_by      text,
    notes           text
);

CREATE INDEX IF NOT EXISTS pending_approvals_status_idx
    ON pending_approvals (status, requested_at DESC);
