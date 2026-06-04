-- Waitlist table. Stores email captures from funnels that collect interest
-- before a flow is available, distinguished by product_name. Used by:
--   - the pre-launch "Coming Soon" page (product_name = 'launch_waitlist')
--
-- Written server-side via the service_role key (RLS bypassed), matching the
-- rest of the app's data access. Apply once against the Supabase project
-- (SQL Editor or psql).

CREATE TABLE IF NOT EXISTS waitlist (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text NOT NULL,
    product_name  text NOT NULL,                       -- e.g. 'launch_waitlist'
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS waitlist_product_created_idx
    ON waitlist (product_name, created_at DESC);
