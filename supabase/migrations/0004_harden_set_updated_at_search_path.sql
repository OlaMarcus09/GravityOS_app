-- Gravity OS — security hardening
-- Pin set_updated_at's search_path (advisor: function_search_path_mutable).
-- An empty search_path is safe here: the function only touches NEW, no
-- unqualified object lookups.
create or replace function set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
