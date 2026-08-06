import { expect, test } from "@playwright/test";

test.describe("public and auth entry points", () => {
  test("landing page has usable auth actions", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Gravity OS/i);
    await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
      "href",
      "/manifest.webmanifest",
    );
    await expect(page.getByRole("link", { name: "Get started" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Log in" }).first()).toBeVisible();
  });

  test("PWA foundation exposes a manifest and network-only service worker", async ({ request }) => {
    const manifestResponse = await request.get("/manifest.webmanifest");
    expect(manifestResponse.ok()).toBeTruthy();
    await expect(manifestResponse.json()).resolves.toMatchObject({
      name: "Gravity OS",
      display: "standalone",
      start_url: "/dashboard",
    });

    const serviceWorkerResponse = await request.get("/sw.js");
    expect(serviceWorkerResponse.ok()).toBeTruthy();
    const serviceWorker = await serviceWorkerResponse.text();
    expect(serviceWorker).toContain('request.mode !== "navigate"');
    expect(serviceWorker).not.toContain("cache.put");

    const offlineResponse = await request.get("/offline.html");
    expect(offlineResponse.ok()).toBeTruthy();
    expect(await offlineResponse.text()).toContain("You’re offline");
  });

  test("signup keeps an unconfirmed user out of the app", async ({ page }) => {
    await page.goto("/signup");
    await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
    await expect(page.locator("input[type=email]")).toHaveAttribute("autocomplete", "email");
    await expect(page.locator("input[type=password]")).toHaveAttribute("autocomplete", "new-password");
  });

  test("invite route explains an invalid or expired link", async ({ page }) => {
    await page.goto("/auth/invite");
    await expect(page.getByText(/invitation link is invalid|expired/i)).toBeVisible({ timeout: 10_000 });
  });
});
