alter table public.catalogue_items
  add column if not exists mime_type text;
