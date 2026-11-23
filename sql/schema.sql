create extension if not exists pgcrypto;

create table if not exists public.research_runs (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid references auth.users(id) on delete cascade,
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

alter table public.research_runs
    add column if not exists owner_id uuid references auth.users(id) on delete cascade;

create index if not exists research_runs_created_at_idx
    on public.research_runs (created_at desc);

create index if not exists research_runs_owner_id_idx
    on public.research_runs (owner_id);

alter table public.research_runs enable row level security;

revoke all on table public.research_runs from anon, authenticated;
grant select, insert, update, delete on table public.research_runs to authenticated;
grant usage on schema public to service_role;
grant select, insert, update, delete on table public.research_runs to service_role;

drop policy if exists "Users can view their own SignalDraft runs" on public.research_runs;
create policy "Users can view their own SignalDraft runs"
    on public.research_runs for select
    to authenticated
    using ((select auth.uid()) = owner_id);

drop policy if exists "Users can create their own SignalDraft runs" on public.research_runs;
create policy "Users can create their own SignalDraft runs"
    on public.research_runs for insert
    to authenticated
    with check ((select auth.uid()) = owner_id);

drop policy if exists "Users can update their own SignalDraft runs" on public.research_runs;
create policy "Users can update their own SignalDraft runs"
    on public.research_runs for update
    to authenticated
    using ((select auth.uid()) = owner_id)
    with check ((select auth.uid()) = owner_id);

drop policy if exists "Users can delete their own SignalDraft runs" on public.research_runs;
create policy "Users can delete their own SignalDraft runs"
    on public.research_runs for delete
    to authenticated
    using ((select auth.uid()) = owner_id);
