import { expect, test } from "@playwright/test";

test("previews, runs, inspects, and safely stops the mock Society", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Run a society. Watch it become." }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Live Society · Mock/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await page.getByRole("button", { name: "Resolve & preview agents" }).click();
  await expect(page.getByText("Resolved configuration")).toBeVisible();
  await expect(page.getByText("3 active agents · seed 97")).toBeVisible();

  await page.getByRole("button", { name: /Start simulation/ }).click();
  await expect(page.getByText("completed", { exact: true })).toBeVisible();
  await expect(page.locator(".feed li")).toHaveCount(3);
  await expect(page.locator(".state-panel pre")).toContainText('"resource": 7');

  await page.getByRole("button", { name: "Resolve & preview agents" }).click();
  await page.getByLabel("Run mode").selectOption("continuous");
  await page.getByLabel("Tick pace").fill("0.2");
  await page.getByRole("button", { name: /Start simulation/ }).click();
  await expect(page.getByText("running", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Stop safely" }).click();
  await expect(page.getByText("stopped", { exact: true })).toBeVisible();
  await expect(page.locator(".state-panel pre")).toContainText('"resource"');
});
