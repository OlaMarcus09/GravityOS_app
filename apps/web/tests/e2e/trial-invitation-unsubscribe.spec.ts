import { expect, test } from "@playwright/test";

test("opt-out requires a click, keeps token out of the URL, and never claims a trial", async ({ page }) => {
  const token = "a".repeat(32) + "." + "b".repeat(64);
  let unsubscribeCalls = 0;
  let claimCalls = 0;
  await page.route("**/api/v1/trial-invitations/unsubscribe", async (route) => {
    unsubscribeCalls += 1;
    expect(route.request().postDataJSON()).toEqual({ token });
    await route.fulfill({ status: 200, json: { unsubscribed: true } });
  });
  await page.route("**/api/v1/billing/existing-trial/claim", async (route) => {
    claimCalls += 1;
    await route.fulfill({ status: 500 });
  });

  await page.goto(`/trial-invitations/unsubscribe#token=${token}`);
  await expect(page.getByRole("heading", { name: "Trial invitation preferences" })).toBeVisible();
  await expect(page).toHaveURL(/\/trial-invitations\/unsubscribe$/);
  expect(unsubscribeCalls).toBe(0);
  await page.getByRole("button", { name: "Unsubscribe" }).click();
  await expect(page.getByText("You are unsubscribed from promotional trial invitations.", { exact: false })).toBeVisible();
  expect(unsubscribeCalls).toBe(1);
  expect(claimCalls).toBe(0);
});
