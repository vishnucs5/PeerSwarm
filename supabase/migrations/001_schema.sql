-- Multi-Agent Research Lab — Supabase Schema
-- Creates persistent storage for research jobs and results

-- ── Jobs Table ──────────────────────────────────────────────────────

create table if not exists jobs (
  id            uuid primary key default gen_random_uuid(),
  question      text not null,
  status        text not null default 'queued'
                check (status in ('queued','planning','researching','analyzing','evaluating','writing','completed','failed')),
  iteration     int not null default 0,
  max_iterations int not null default 3,
  quality_score jsonb,
  error         text,
  tags          text[] default '{}',
  priority      text not null default 'normal'
                check (priority in ('low','normal','high')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- ── Job Results Table ───────────────────────────────────────────────

create table if not exists job_results (
  id                uuid primary key default gen_random_uuid(),
  job_id            uuid not null references jobs(id) on delete cascade,
  question          text not null,
  executive_summary text,
  key_takeaways     jsonb,
  "references"      jsonb,
  sections          jsonb,
  report_markdown   text,
  report            jsonb,
  quality_score     jsonb,
  duration_seconds  float,
  iterations        int,
  created_at        timestamptz not null default now()
);

-- ── Indexes ─────────────────────────────────────────────────────────

create index if not exists idx_jobs_status       on jobs(status);
create index if not exists idx_jobs_created_at   on jobs(created_at desc);
create index if not exists idx_job_results_job_id on job_results(job_id);

-- ── Row Level Security ──────────────────────────────────────────────

alter table jobs       enable row level security;
alter table job_results enable row level security;

-- Allow anon access for development (adjust for production)
create policy "Allow anon read jobs"
  on jobs for select
  to anon
  using (true);

create policy "Allow anon insert jobs"
  on jobs for insert
  to anon
  with check (true);

create policy "Allow anon update jobs"
  on jobs for update
  to anon
  using (true);

create policy "Allow anon read job_results"
  on job_results for select
  to anon
  using (true);

create policy "Allow anon insert job_results"
  on job_results for insert
  to anon
  with check (true);
