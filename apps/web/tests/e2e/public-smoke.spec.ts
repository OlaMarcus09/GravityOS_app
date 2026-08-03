import { expect, test } from "@playwright/test";

test.describe("public and auth entry points", () => {
  test("landing page has usable auth actions", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Gravity OS/i);
    await expect(page.getByRole("link", { name: "Get started" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Log in" }).first()).toBeVisible();
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
