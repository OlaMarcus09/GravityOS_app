# Supabase production verification

The migrations and API contain the signup trigger, personal workspace
provisioning, tenant RLS policies, CRUD routes, storage-backed catalogue, and
Gravity Score persistence. Use the verification script before a beta release
or after applying migrations to a new project.

From `apps/api`:

```bash
python3 scripts/verify_supabase.py                 # dry run; no network calls
python3 scripts/verify_supabase.py --live          # auth, membership, RLS reads, dashboard
python3 scripts/verify_supabase.py --live --mutate # also score compute and CRUD with cleanup
```

Live mode requires an existing test account (do not use a production user's
password):

```bash
export SUPABASE_URL=https://<project>.supabase.co
export SUPABASE_ANON_KEY=<anon-key>
export API_URL=https://<api-origin>
export GRAVITY_TEST_EMAIL=gravity-smoke@example.com
export GRAVITY_TEST_PASSWORD='use-a-test-only-password'
```

For invitation emails, set `WEB_APP_URL` on the API deployment to the public
web origin (for example `https://gravity-os-app.vercel.app`) and add both the
local and production callback URLs to Supabase Auth redirect URLs:

```text
http://localhost:3000/auth/invite
https://gravity-os-app.vercel.app/auth/invite
```

The full run verifies:

- password sign-in through Supabase Auth;
- profile and default workspace provisioning after signup;
- workspace membership and `X-Workspace-Id` tenant scoping;
- dashboard aggregation and Gravity Score reads;
- Gravity Score computation/write persistence in `--mutate` mode;
- project, task, and calendar create/update/list/delete behavior (with cleanup).

For a clean-project manual check, create a new user in Supabase Auth and
confirm that `profiles`, `workspaces`, and `workspace_members` each receive one
row from the signup trigger before running the script. Then repeat with a
second workspace/member and confirm the first user's token cannot read the
second workspace when its ID is supplied in `X-Workspace-Id`.

Catalogue binary upload/download and deletion are intentionally verified by
the catalogue lifecycle workstream, not this script.
