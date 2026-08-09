create extension if not exists pg_trgm;

create or replace function public.match_document_chunks(
  query_embedding vector(1024),
  match_threshold double precision,
  match_count integer,
  p_user_id uuid,
  p_document_id uuid
)
returns table (
  chunk_id uuid,
  document_id uuid,
  user_id uuid,
  chunk_index integer,
  content text,
  page_start integer,
  page_end integer,
  metadata jsonb,
  score double precision
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    dc.id as chunk_id,
    dc.document_id,
    dc.user_id,
    dc.chunk_index,
    dc.content,
    dc.page_start,
    dc.page_end,
    dc.metadata,
    (1 - (dc.embedding <=> query_embedding))::double precision as score
  from public.document_chunks dc
  where dc.user_id = p_user_id
    and dc.document_id = p_document_id
    and dc.embedding is not null
    and (1 - (dc.embedding <=> query_embedding)) >= match_threshold
  order by dc.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;

create or replace function public.search_document_chunks_keyword(
  p_query text,
  match_count integer,
  p_user_id uuid,
  p_document_id uuid
)
returns table (
  chunk_id uuid,
  document_id uuid,
  user_id uuid,
  chunk_index integer,
  content text,
  page_start integer,
  page_end integer,
  metadata jsonb,
  score double precision
)
language sql
stable
security invoker
set search_path = public
as $$
  with ranked as (
    select
      dc.id as chunk_id,
      dc.document_id,
      dc.user_id,
      dc.chunk_index,
      dc.content,
      dc.page_start,
      dc.page_end,
      dc.metadata,
      greatest(
        similarity(lower(dc.content), lower(coalesce(p_query, ''))),
        case when lower(dc.content) like '%' || lower(coalesce(p_query, '')) || '%' then 1.0 else 0.0 end
      )::double precision as score
    from public.document_chunks dc
    where dc.user_id = p_user_id
      and dc.document_id = p_document_id
  )
  select *
  from ranked
  where score > 0
  order by score desc
  limit greatest(match_count, 1);
$$;

grant execute on function public.match_document_chunks(vector(1024), double precision, integer, uuid, uuid) to authenticated, service_role;
grant execute on function public.search_document_chunks_keyword(text, integer, uuid, uuid) to authenticated, service_role;
