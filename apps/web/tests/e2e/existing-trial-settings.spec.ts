import { expect, test } from "@playwright/test";

const workspace = "10000000-0000-0000-0000-000000000001";
const expiry = "2026-11-09T12:00:00+00:00";
test.use({ timezoneId: "UTC" });

test("an eligible owner can claim from Settings and see the exact expiry", async ({ page, context }) => {
  const expiresAt = Math.floor(Date.now() / 1000) + 3600;
  const session = {
    access_token: "browser-test-token", refresh_token: "browser-test-refresh",
    token_type: "bearer", expires_in: 3600, expires_at: expiresAt,
    user: { id: "00000000-0000-0000-0000-000000000001", aud: "authenticated",
      role: "authenticated", email: "owner@example.com", created_at: "2026-10-01T00:00:00Z",
      app_metadata: {}, user_metadata: {} },
  };
  await context.addCookies([{ name: "sb-example-auth-token", value: JSON.stringify(session),
    url: "http://127.0.0.1:3000" }]);
  let claimed = false;
  await page.route("http://127.0.0.1:8000/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = [];
    if (path === "/api/v1/me") body = {
      user_id: session.user.id, email: session.user.email, capabilities: { platform_admin: false },
      profile: null, memberships: [{ workspace_id: workspace, role: "owner",
        workspaces: { name: "My Workspace", plan: claimed ? "pro" : "free", type: "personal" } }],
    };
    else if (path === "/api/v1/billing/details") body = {
      plan: claimed ? "pro" : "free", billing_status: "none", trial_status: claimed ? "active" : "none",
      trial_started_at: claimed ? "2026-11-02T12:00:00+00:00" : null,
      trial_expires_at: claimed ? expiry : null, current_period_start: null,
      current_period_end: null, checkout_eligible: false,
    };
    else if (path === "/api/v1/billing/existing-trial/eligibility") body = {
      eligible: !claimed, reason: claimed ? "already_claimed" : "eligible", message: null,
    };
    else if (path === "/api/v1/notifications/preferences") body = {
      user_id: session.user.id, email_enabled: true, in_app_enabled: true,
      task_assignments: true, mentions: true, approval_updates: true,
      deadline_reminders: true, activation_nudges: true, weekly_digests: true,
      dormant_checkins: true, reminder_days_before: [3, 1, 0],
    };
    else if (path === "/api/v1/billing/existing-trial/claim") {
      expect(route.request().headers()["x-workspace-id"]).toBe(workspace);
      claimed = true;
      body = { reason: "activated", trial_started_at: "2026-11-02T12:00:00+00:00",
        trial_expires_at: expiry };
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/settings");
  await expect(page.getByText("You're invited to enjoy seven days of GravityOS Pro, free.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Claim My Trial" }).click();
  const activeStatus = page.getByText("Seven-day Pro trial active", { exact: false });
  await expect(activeStatus).toBeVisible();
  await expect(activeStatus).toContainText(/November 9, 2026.*12:00/);
  await expect(page.getByRole("button", { name: "Claim My Trial" })).toHaveCount(0);
  expect(claimed).toBe(true);
});
