-- Ingestion tracking
CREATE TABLE IF NOT EXISTS public.ingestion_logs (
  id bigint primary key generated always as identity,
  paper_id text,
  title text,
  topic_cluster text,
  evidence_level text,
  year integer,
  ingestion_date text,
  chunks_created integer,
  status text,
  error_message text,
  created_at timestamptz default now()
);

-- Agent failure tracking
CREATE TABLE IF NOT EXISTS public.agent_failures (
  id bigint primary key generated always as identity,
  session_id text,
  query text,
  failed_check text,
  root_cause text,
  exit_reason text,
  resolved bool default false,
  created_at timestamptz default now()
);

-- Background repair tracking
CREATE TABLE IF NOT EXISTS public.repair_history (
  id bigint primary key generated always as identity,
  repair_type text,
  paper_ids text,
  root_cause text,
  chunks_affected integer,
  success_count integer,
  error_count integer,
  duration_seconds float,
  created_at timestamptz default now()
);

-- Admin approval queue
CREATE TABLE IF NOT EXISTS public.repair_queue (
  id bigint primary key generated always as identity,
  session_id text,
  query text,
  failure_class text,
  root_cause text,
  confidence float,
  status text default 'pending',
  created_at timestamptz default now()
);

-- Agent 6 patterns
CREATE TABLE IF NOT EXISTS public.agent6_patterns (
  id bigint primary key generated always as identity,
  pattern_id text unique,
  topic_cluster text,
  failure_type text,
  occurrence_count integer default 1,
  first_seen timestamptz default now(),
  last_seen timestamptz default now(),
  sample_queries text,
  severity text default 'low',
  recommended_action text,
  created_at timestamptz default now()
);

-- Agent 6 coverage gaps
CREATE TABLE IF NOT EXISTS public.agent6_gaps (
  id bigint primary key generated always as identity,
  topic text unique,
  query_count integer default 1,
  coverage_level text default 'none',
  first_detected timestamptz default now(),
  last_queried timestamptz default now(),
  sample_queries text,
  created_at timestamptz default now()
);

-- Agent 6 calibration
CREATE TABLE IF NOT EXISTS public.agent6_calibration (
  id bigint primary key generated always as identity,
  topic_cluster text unique,
  expressed_confidence float,
  actual_pass_rate float,
  sample_size integer default 0,
  last_updated timestamptz default now()
);

-- Agent 6 insights
CREATE TABLE IF NOT EXISTS public.agent6_insights (
  id bigint primary key generated always as identity,
  insight_id text unique,
  insight_type text,
  title text,
  description text,
  evidence text,
  recommended_action text,
  priority text default 'medium',
  created_at timestamptz default now(),
  status text default 'new'
);

-- Benchmark questions
CREATE TABLE IF NOT EXISTS public.benchmark_questions (
  id bigint primary key generated always as identity,
  question_id text unique,
  question text,
  expected_answer text,
  topic_cluster text,
  difficulty text,
  source_pmid text,
  created_at timestamptz default now()
);

-- Benchmark results
CREATE TABLE IF NOT EXISTS public.benchmark_results (
  id bigint primary key generated always as identity,
  run_id text,
  question_id text,
  question text,
  generated_answer text,
  confidence float,
  agent2_passed bool,
  cycle_ran bool,
  cache_hit bool,
  processing_time_ms integer,
  manual_score float default null,
  created_at timestamptz default now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ingestion_status 
  ON public.ingestion_logs(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_cluster 
  ON public.ingestion_logs(topic_cluster);
CREATE INDEX IF NOT EXISTS idx_benchmark_run 
  ON public.benchmark_results(run_id);
CREATE INDEX IF NOT EXISTS idx_failures_session 
  ON public.agent_failures(session_id);
