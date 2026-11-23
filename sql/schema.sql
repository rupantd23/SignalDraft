create extension if not exists pgcrypto;

create table if not exists public.research_runs (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    prospect_name text not null,
    company_name text not null,
    outcome text not null check (
        outcome in ('draft_ready', 'needs_clarification', 'abstained', 'failed')
    ),
    review_status text not null default 'pending' check (
        review_status in ('pending', 'approved', 'rejected')
    ),
    payload jsonb not null
);

create index if not exists research_runs_created_at_idx
    on public.research_runs (created_at desc);
