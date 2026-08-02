# Gravity OS

Gravity OS is a workspace for independent creators and creative teams. It brings projects, tasks, release planning, catalogue management, budgets, marketing, calendar planning, collaboration, notifications, and Gravity Score insights into one authenticated product.

The repository contains a Next.js web app, a FastAPI API, and versioned Supabase migrations. The project is currently in MVP alpha and is being tested with early users.

## What is included

- Authentication with Supabase Auth
- Automatic personal workspace provisioning at signup
- Workspace roles: owner, admin, member, and viewer
- Projects, tasks, assignments, comments, mentions, and activity history
- Team invitations and notification delivery
- Calendar and release planning
- Catalogue uploads using signed Supabase Storage URLs
- Budget and marketing planning
- Plan-based feature gates for Free, Pro, and Team workspaces
- Gravity Score computation and protected score snapshots
- Task approval workflows for Team workspaces
- Platform administration with manual plan management, audit history, user search, and account suspension/reactivation

Billing, live AI Manager generation, offline access, marketplace features, and mobile applications are intentionally deferred while the MVP is validated.

## Technology

| Area | Technology |
| --- | --- |
| Web | Next.js 14, React 18, TypeScript |
| API | FastAPI, Pydantic, Python 3.11+ |
| Data | Supabase Postgres, PostgREST, Row Level Security |
| Identity | Supabase Auth |
| Storage | Supabase Storage |
| Hosting | Vercel for web, Render for API |
| Client data | TanStack Query |

## Repository layout

```text
apps/
  api/       FastAPI service, routers, schemas, and tests
  web/       Next.js App Router application
supabase/
  migrations/ Versioned database schema and RLS changes
docs/
  ARCHITECTURE.md  Technical architecture and delivery status
  PRD.md           Product requirements
  revenue-engine.md Product and revenue notes
render.yaml        Render API deployment configuration
```

## Prerequisites

- Node.js 18 or newer
- npm
- Python 3.11 or newer
- A Supabase project with Auth, Postgres, and Storage enabled

## Local setup

Clone the repository and install the two application packages:

```bash
git clone https://github.com/OlaMarcus09/GravityOS_app.git
cd GravityOS_app

cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

cd ../web
npm install
```

Create `apps/api/.env` from `apps/api/.env.example`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_JWT_AUD=authenticated
CORS_ORIGINS=http://localhost:3000
WEB_APP_URL=http://localhost:3000
SUPER_ADMIN_EMAILS=
ENVIRONMENT=development
```

Create `apps/web/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Apply migrations in order through the Supabase dashboard, Supabase CLI, or your migration workflow. The latest migrations include collaboration, security hardening, audited admin controls, and Team task approvals.

Start both services in separate terminals:

```bash
# Terminal 1
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2
cd apps/web
npm run dev
```

Open `http://localhost:3000`.

## Tests and verification

Run the API test suite:

```bash
cd apps/api
.venv/bin/pytest -q
```

Run the frontend checks:

```bash
cd apps/web
npm run typecheck
npm run build
```

The API tests cover authentication boundaries, workspace permissions, tenancy references, collaboration, notifications, security hardening, error contracts, admin controls, and task approvals.

## Deployment

The intended deployment topology is:

- Web app: Vercel, rooted at `apps/web`
- API: Render, configured by `render.yaml`, rooted at `apps/api`
- Database and Auth: Supabase

Set the API environment variables in Render. In particular, `SUPER_ADMIN_EMAILS` must contain the verified platform administrator email. It is intentionally empty in the repository example and is not hard-coded in the API.

When deploying a new database migration, apply it before testing the corresponding release. Current product migrations are numbered through `0017_team_workflow_integrity.sql`.

## Security model

Gravity OS is multi-tenant. The API checks the active workspace, membership, role, and plan for every workspace request. Supabase Row Level Security provides the database backstop. Viewer members can read workspace data but cannot mutate it. Service-role access is reserved for server-owned writes and platform administration.

Do not commit `.env`, service-role keys, JWT secrets, or production credentials. Use environment variables in Render, Vercel, and local development.

## Product status

Gravity OS is an MVP alpha. The core creator workflow is available, but production verification is still in progress. The current priority is user testing and workflow refinement. Planned follow-up work includes broader approval workflows, production invitation-email verification, live AI Manager outputs, offline access, and marketplace features. Billing and mobile apps will be revisited after the product has more usage data.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the detailed system design and delivery roadmap.

## Contributing

Keep changes scoped to the relevant app or migration, add regression tests for API behavior and permissions, and run the API suite plus frontend typecheck before opening a pull request. Database changes must use a new numbered migration and preserve tenant isolation.

## License

No open-source license has been declared yet. Contact the repository owner before redistributing or using the code outside the project.
