-- DDL to create benchmarking tables for FailureRAG

-- 1. Table for benchmark questions
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

-- 2. Table for benchmark run results
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

-- 3. Index to optimize run_id aggregations
CREATE INDEX IF NOT EXISTS idx_benchmark_run 
ON public.benchmark_results(run_id);
