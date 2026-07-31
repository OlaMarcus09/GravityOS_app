-- Prevent foreign keys from joining records across workspace boundaries.

create or replace function public.prevent_workspace_reassignment()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.workspace_id is distinct from old.workspace_id then
    raise exception 'workspace_id cannot be changed'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

do $$
declare
  tenant_table text;
begin
  foreach tenant_table in array array[
    'projects',
    'tasks',
    'calendar_events',
    'release_plans',
    'catalogue_items',
    'budgets',
    'campaigns',
    'content_pieces'
  ]
  loop
    execute format(
      'drop trigger if exists trg_%s_workspace_immutable on public.%I',
      tenant_table,
      tenant_table
    );
    execute format(
      'create trigger trg_%s_workspace_immutable
         before update of workspace_id on public.%I
         for each row execute function public.prevent_workspace_reassignment()',
      tenant_table,
      tenant_table
    );
  end loop;
end;
$$;

create or replace function public.enforce_project_workspace_reference()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.project_id is not null and not exists (
    select 1
    from public.projects p
    where p.id = new.project_id
      and p.workspace_id = new.workspace_id
  ) then
    raise exception 'project must belong to the same workspace'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

do $$
declare
  tenant_table text;
begin
  foreach tenant_table in array array[
    'tasks',
    'calendar_events',
    'release_plans',
    'catalogue_items',
    'budgets',
    'campaigns'
  ]
  loop
    execute format(
      'drop trigger if exists trg_%s_project_workspace on public.%I',
      tenant_table,
      tenant_table
    );
    execute format(
      'create trigger trg_%s_project_workspace
         before insert or update of project_id, workspace_id on public.%I
         for each row execute function public.enforce_project_workspace_reference()',
      tenant_table,
      tenant_table
    );
  end loop;
end;
$$;

create or replace function public.enforce_campaign_workspace_reference()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1
    from public.campaigns c
    where c.id = new.campaign_id
      and c.workspace_id = new.workspace_id
  ) then
    raise exception 'campaign must belong to the same workspace'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_content_pieces_campaign_workspace on public.content_pieces;
create trigger trg_content_pieces_campaign_workspace
before insert or update of campaign_id, workspace_id on public.content_pieces
for each row execute function public.enforce_campaign_workspace_reference();
