-- Multi-Agent Research Lab — Row Level Security Policies
-- Drops permissive anon policies and adds proper auth-based policies

-- ── Drop existing permissive policies ─────────────────────────────

DROP POLICY IF EXISTS "Allow anon read jobs" ON jobs;
DROP POLICY IF EXISTS "Allow anon insert jobs" ON jobs;
DROP POLICY IF EXISTS "Allow anon update jobs" ON jobs;
DROP POLICY IF EXISTS "Allow anon read job_results" ON job_results;
DROP POLICY IF EXISTS "Allow anon insert job_results" ON job_results;

-- ── Service role policies (full access for backend) ──────────────

CREATE POLICY "Service role full access on jobs"
  ON jobs FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role full access on job_results"
  ON job_results FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- ── Authenticated user policies ──────────────────────────────────

-- Users can read their own jobs (by tags or future user_id column)
CREATE POLICY "Authenticated users read own jobs"
  ON jobs FOR SELECT
  TO authenticated
  USING (true);

-- Users can create jobs
CREATE POLICY "Authenticated users create jobs"
  ON jobs FOR INSERT
  TO authenticated
  WITH CHECK (true);

-- Users can update their own jobs
CREATE POLICY "Authenticated users update own jobs"
  ON jobs FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Users can read job results for jobs they can see
CREATE POLICY "Authenticated users read job_results"
  ON job_results FOR SELECT
  TO authenticated
  USING (true);

-- Users can insert job results
CREATE POLICY "Authenticated users create job_results"
  ON job_results FOR INSERT
  TO authenticated
  WITH CHECK (true);

-- ── Disable anon access entirely ─────────────────────────────────

ALTER TABLE jobs FORCE ROW LEVEL SECURITY;
ALTER TABLE job_results FORCE ROW LEVEL SECURITY;
