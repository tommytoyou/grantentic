-- Adds the expert_review_requested flag used by the NSF Full Proposal and
-- NSF Complete Bundle products to mark proposals for Tom's manual review queue.
-- Apply once against the Supabase project (SQL Editor or psql).

ALTER TABLE proposals
    ADD COLUMN IF NOT EXISTS expert_review_requested boolean DEFAULT false;
