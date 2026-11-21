-- Supabase baseline corpus for article-level vector-search comparisons.
-- The dimension is provisional (1024) and must match the selected embed model.

create extension if not exists vector with schema extensions;

create table if not exists public.baseline_chunks (
    id text primary key,
    doc_id text not null,
    doc_title text not null,
    doc_type text,
    authority_rank smallint,
    effective_date text,
    article_no text not null,
    article_title text,
    chunk_text text not null,
    source_kind text not null default 'internal',
    source_file text,
    embedding extensions.vector(1024),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint baseline_chunks_source_kind_check
        check (source_kind in ('internal', 'law'))
);

create index if not exists baseline_chunks_doc_id_idx
    on public.baseline_chunks (doc_id);

create index if not exists baseline_chunks_source_kind_idx
    on public.baseline_chunks (source_kind);

alter table public.baseline_chunks enable row level security;

drop policy if exists baseline_chunks_read_public_corpus
    on public.baseline_chunks;
create policy baseline_chunks_read_public_corpus
    on public.baseline_chunks
    for select
    to anon, authenticated
    using (true);

grant select on public.baseline_chunks to anon, authenticated;
grant select, insert, update, delete on public.baseline_chunks to service_role;

comment on table public.baseline_chunks is
    'Article-level corpus for vector-only RAG baseline; embedding may remain null until model selection.';
comment on column public.baseline_chunks.embedding is
    'Nullable pgvector embedding. Current 1024 dimension is provisional and must match EMBED_MODEL.';
