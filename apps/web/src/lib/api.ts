import { supabase } from "@/lib/supabase";

// Typed FastAPI client (ARCHITECTURE.md section 1 & 4).
// Attaches the Supabase access token as a Bearer header, and the active
// workspace via X-Workspace-Id (per section 3).

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type ApiOptions = {
  method?: string;
  body?: unknown;
  workspaceId?: string;
};

export async function apiFetch<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }
  if (opts.workspaceId) {
    headers["X-Workspace-Id"] = opts.workspaceId;
  }

  const res = await fetch(`${API_URL}/api/v1${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) {
    let message = res.statusText;
    let code: string | undefined;
    try {
      const payload = await res.json();
      message = payload?.error?.message ?? message;
      code = payload?.error?.code;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, message, code);
  }

  return res.json() as Promise<T>;
}

// --- Response types (mirror API schemas; expanded per feature) ------------

export type Membership = {
  workspace_id: string;
  role: "owner" | "admin" | "member" | "viewer";
  workspaces: { name: string; plan: string; type: string } | null;
};

export type MeResponse = {
  user_id: string;
  email: string | null;
  profile: {
    id: string;
    display_name: string | null;
    avatar_url: string | null;
    creative_role: string | null;
    timezone: string | null;
  } | null;
  memberships: Membership[];
};

export function getMe() {
  return apiFetch<MeResponse>("/me");
}

// --- Tasks -----------------------------------------------------------------

export type TaskStatus = "todo" | "in_progress" | "blocked" | "done";
export type Priority = "low" | "medium" | "high";

export type Task = {
  id: string;
  workspace_id: string;
  project_id: string | null;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: Priority;
  due_date: string | null;
  assignee_id: string | null;
  created_by: string | null;
  completed_at: string | null;
};

export type TaskInput = {
  title: string;
  project_id?: string | null;
  description?: string | null;
  status?: TaskStatus;
  priority?: Priority;
  due_date?: string | null;
};

export const tasksApi = {
  list: (ws: string, params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return apiFetch<Task[]>(`/tasks${qs}`, { workspaceId: ws });
  },
  create: (ws: string, body: TaskInput) =>
    apiFetch<Task>("/tasks", { method: "POST", body, workspaceId: ws }),
  update: (ws: string, id: string, body: Partial<TaskInput> & { completed_at?: string | null }) =>
    apiFetch<Task>(`/tasks/${id}`, { method: "PATCH", body, workspaceId: ws }),
  remove: (ws: string, id: string) =>
    apiFetch<void>(`/tasks/${id}`, { method: "DELETE", workspaceId: ws }),
};
// --- Projects --------------------------------------------------------------

export type ProjectStatus = "idea" | "in_progress" | "ready" | "released" | "archived";

export type Project = {
  id: string;
  workspace_id: string;
  title: string;
  type: string;
  status: ProjectStatus;
  cover_url: string | null;
  target_release_date: string | null;
  description: string | null;
  created_by: string | null;
};

export type ProjectInput = {
  title: string;
  type?: string;
  status?: ProjectStatus;
  target_release_date?: string | null;
  description?: string | null;
};

export const projectsApi = {
  list: (ws: string) => apiFetch<Project[]>("/projects", { workspaceId: ws }),
  get: (ws: string, id: string) => apiFetch<Project>(`/projects/${id}`, { workspaceId: ws }),
  create: (ws: string, body: ProjectInput) =>
    apiFetch<Project>("/projects", { method: "POST", body, workspaceId: ws }),
  update: (ws: string, id: string, body: Partial<ProjectInput>) =>
    apiFetch<Project>(`/projects/${id}`, { method: "PATCH", body, workspaceId: ws }),
  remove: (ws: string, id: string) =>
    apiFetch<void>(`/projects/${id}`, { method: "DELETE", workspaceId: ws }),
};
// --- Calendar --------------------------------------------------------------

export type CalendarEvent = {
  id: string;
  workspace_id: string;
  title: string;
  type: string;
  starts_at: string;
  ends_at: string | null;
  all_day: boolean;
  project_id: string | null;
  notes: string | null;
};

export type CalendarTaskDue = {
  id: string;
  title: string;
  due_date: string;
  status: TaskStatus;
};

export type CalendarProjectRelease = {
  id: string;
  title: string;
  target_release_date: string;
  status: ProjectStatus;
  type: string;
};

export type CalendarCampaign = {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
  objective: string;
  project_id: string | null;
};

export type CalendarContent = {
  id: string;
  caption: string | null;
  platform: string;
  format: string;
  scheduled_at: string;
  status: string;
  campaign_id: string;
};

export type CalendarMilestone = {
  id: string;
  title: string;
  due_date: string;
  status: string;
  category: string;
  release_plan_id: string;
};

export type CalendarResponse = {
  events: CalendarEvent[];
  task_due_dates: CalendarTaskDue[];
  project_releases: CalendarProjectRelease[];
  campaigns: CalendarCampaign[];
  scheduled_content: CalendarContent[];
  milestones: CalendarMilestone[];
};

export type EventInput = {
  title: string;
  type?: string;
  starts_at: string;
  ends_at?: string | null;
  all_day?: boolean;
  project_id?: string | null;
  notes?: string | null;
};

export const calendarApi = {
  range: (ws: string, from?: string, to?: string) => {
    const p = new URLSearchParams();
    if (from) p.set("from", from);
    if (to) p.set("to", to);
    const qs = p.toString() ? `?${p.toString()}` : "";
    return apiFetch<CalendarResponse>(`/calendar${qs}`, { workspaceId: ws });
  },
  create: (ws: string, body: EventInput) =>
    apiFetch<CalendarEvent>("/calendar/events", { method: "POST", body, workspaceId: ws }),
  update: (ws: string, id: string, body: Partial<EventInput>) =>
    apiFetch<CalendarEvent>(`/calendar/events/${id}`, { method: "PATCH", body, workspaceId: ws }),
  remove: (ws: string, id: string) =>
    apiFetch<void>(`/calendar/events/${id}`, { method: "DELETE", workspaceId: ws }),
};
// --- Budgets ---------------------------------------------------------------

export type Budget = {
  id: string;
  workspace_id: string;
  name: string;
  total_amount: string;
  currency: string;
  project_id: string | null;
};

export type BudgetItem = {
  id: string;
  budget_id: string;
  category: string;
  label: string;
  planned_amount: string;
  actual_amount: string | null;
  spent_at: string | null;
};

export type BudgetInput = {
  name: string;
  total_amount: number;
  currency?: string;
  project_id?: string | null;
};

export type BudgetItemInput = {
  category: string;
  label: string;
  planned_amount: number;
  actual_amount?: number | null;
  spent_at?: string | null;
};

export const budgetsApi = {
  list: (ws: string) => apiFetch<Budget[]>("/budgets", { workspaceId: ws }),
  create: (ws: string, body: BudgetInput) =>
    apiFetch<Budget>("/budgets", { method: "POST", body, workspaceId: ws }),
  update: (ws: string, id: string, body: Partial<BudgetInput>) =>
    apiFetch<Budget>(`/budgets/${id}`, { method: "PATCH", body, workspaceId: ws }),
  addItem: (ws: string, budgetId: string, body: BudgetItemInput) =>
    apiFetch<BudgetItem>(`/budgets/${budgetId}/items`, { method: "POST", body, workspaceId: ws }),
  updateItem: (ws: string, itemId: string, body: Partial<BudgetItemInput>) =>
    apiFetch<BudgetItem>(`/budget-items/${itemId}`, { method: "PATCH", body, workspaceId: ws }),
  removeItem: (ws: string, itemId: string) =>
    apiFetch<void>(`/budget-items/${itemId}`, { method: "DELETE", workspaceId: ws }),
};
// --- Marketing -------------------------------------------------------------

export type Campaign = {
  id: string;
  workspace_id: string;
  name: string;
  objective: string;
  status: string;
  start_date: string;
  end_date: string;
  project_id: string | null;
};

export type ContentPiece = {
  id: string;
  campaign_id: string;
  workspace_id: string;
  platform: string;
  format: string;
  scheduled_at: string | null;
  status: string;
  caption: string | null;
};

export type CampaignInput = {
  name: string;
  objective: string;
  status?: string;
  start_date: string;
  end_date: string;
  project_id?: string | null;
};

export type ContentInput = {
  platform: string;
  format: string;
  scheduled_at?: string | null;
  status?: string;
  caption?: string | null;
};

export const marketingApi = {
  list: (ws: string) => apiFetch<Campaign[]>("/campaigns", { workspaceId: ws }),
  create: (ws: string, body: CampaignInput) =>
    apiFetch<Campaign>("/campaigns", { method: "POST", body, workspaceId: ws }),
  update: (ws: string, id: string, body: Partial<CampaignInput>) =>
    apiFetch<Campaign>(`/campaigns/${id}`, { method: "PATCH", body, workspaceId: ws }),
  addContent: (ws: string, campaignId: string, body: ContentInput) =>
    apiFetch<ContentPiece>(`/campaigns/${campaignId}/content`, { method: "POST", body, workspaceId: ws }),
  updateContent: (ws: string, contentId: string, body: Partial<ContentInput>) =>
    apiFetch<ContentPiece>(`/content/${contentId}`, { method: "PATCH", body, workspaceId: ws }),
  removeContent: (ws: string, contentId: string) =>
    apiFetch<void>(`/content/${contentId}`, { method: "DELETE", workspaceId: ws }),
};
// --- Catalogue -------------------------------------------------------------

export type CatalogueItem = {
  id: string;
  workspace_id: string;
  project_id: string | null;
  title: string;
  kind: string;
  status: string;
  isrc: string | null;
  bpm: number | null;
  key: string | null;
  file_size: number | null;
  storage_path: string;
  tags: string[];
  created_at: string;
};

export type CatalogueInput = {
  title: string;
  kind: string;
  project_id?: string | null;
  status?: string;
  isrc?: string | null;
  bpm?: number | null;
  key?: string | null;
  file_size?: number | null;
  tags?: string[];
};

export const catalogueApi = {
  list: (ws: string, params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return apiFetch<CatalogueItem[]>(`/catalogue${qs}`, { workspaceId: ws });
  },
  // Returns the created row plus a signed `upload_url` for the file PUT.
  create: (ws: string, body: CatalogueInput) =>
    apiFetch<CatalogueItem & { upload_url: string }>("/catalogue", {
      method: "POST",
      body,
      workspaceId: ws,
    }),
  // Returns the row plus a signed `download_url`.
  get: (ws: string, id: string) =>
    apiFetch<CatalogueItem & { download_url: string }>(`/catalogue/${id}`, { workspaceId: ws }),
  update: (ws: string, id: string, body: Partial<CatalogueInput>) =>
    apiFetch<CatalogueItem>(`/catalogue/${id}`, { method: "PATCH", body, workspaceId: ws }),
  remove: (ws: string, id: string) =>
    apiFetch<void>(`/catalogue/${id}`, { method: "DELETE", workspaceId: ws }),
};
// --- Releases --------------------------------------------------------------

export type Milestone = {
  id: string;
  release_plan_id: string;
  title: string;
  category: string;
  due_date: string | null;
  status: string;
  position: number;
};

export type ReleasePlan = {
  id: string;
  workspace_id: string;
  project_id: string;
  release_date: string;
  status: string;
  release_milestones?: Milestone[];
};

export type ReleasePlanInput = {
  release_date: string;
  status?: string;
};

export type MilestoneInput = {
  title: string;
  category: string;
  due_date?: string | null;
  status?: string;
  position?: number;
};

export const releasesApi = {
  get: (ws: string, projectId: string) =>
    apiFetch<ReleasePlan>(`/projects/${projectId}/release-plan`, { workspaceId: ws }),
  create: (ws: string, projectId: string, body: ReleasePlanInput) =>
    apiFetch<ReleasePlan>(`/projects/${projectId}/release-plan`, {
      method: "POST",
      body,
      workspaceId: ws,
    }),
  update: (ws: string, planId: string, body: Partial<ReleasePlanInput>) =>
    apiFetch<ReleasePlan>(`/release-plans/${planId}`, { method: "PATCH", body, workspaceId: ws }),
  addMilestone: (ws: string, planId: string, body: MilestoneInput) =>
    apiFetch<Milestone>(`/release-plans/${planId}/milestones`, {
      method: "POST",
      body,
      workspaceId: ws,
    }),
  updateMilestone: (ws: string, id: string, body: Partial<MilestoneInput>) =>
    apiFetch<Milestone>(`/milestones/${id}`, { method: "PATCH", body, workspaceId: ws }),
  removeMilestone: (ws: string, id: string) =>
    apiFetch<void>(`/milestones/${id}`, { method: "DELETE", workspaceId: ws }),
};

// --- Dashboard + intelligence ---------------------------------------------

export type GravityScore = {
  id: string;
  workspace_id: string;
  score: number;
  computed_at: string;
} | null;

export type AiOutput = {
  id: string;
  workspace_id: string;
  kind: string;
  content: unknown;
  generated_at: string;
};

export type DashboardResponse = {
  tasks_due_today: Task[];
  tasks_overdue: Task[];
  upcoming_events: CalendarEvent[];
  upcoming_milestones: Milestone[];
  gravity_score: GravityScore;
  latest_ai_output: AiOutput | null;
  project_count: number;
  task_count: number;
  catalogue_count: number;
  has_release_plan: boolean;
};

export const dashboardApi = {
  get: (ws: string) => apiFetch<DashboardResponse>("/dashboard", { workspaceId: ws }),
};
