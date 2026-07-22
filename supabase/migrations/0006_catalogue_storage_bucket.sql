-- Gravity OS — Catalogue Vault storage bucket
-- The catalogue router (apps/api/app/routers/catalogue.py) uploads/downloads
-- files exclusively through the SERVICE-ROLE client via signed URLs:
--   * POST /catalogue  -> create_signed_upload_url(bucket='catalogue', path)
--   * GET  /catalogue/{id} -> create_signed_url(bucket='catalogue', path, 3600)
-- Storage path is `{workspace_id}/{title}`. Files never stream through the API
-- and the browser only ever receives time-limited signed URLs.
--
-- Because all access is mediated by the service role (which bypasses Storage
-- RLS), the bucket MUST be private and needs NO storage.objects policies:
-- anon/authenticated clients never touch Storage directly.
--
-- Idempotent so `supabase db reset` replays cleanly.
insert into storage.buckets (id, name, public)
values ('catalogue', 'catalogue', false)
on conflict (id) do update set public = excluded.public;
