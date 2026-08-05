-- Reserve the Enterprise workspace tier for deferred organization features.
-- Product/UI plan selection remains deferred; this only extends the schema.
alter type public.workspace_plan add value if not exists 'enterprise';
