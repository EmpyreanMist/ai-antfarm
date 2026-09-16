import { expect, test } from "@playwright/test";

test("previews, runs, inspects, and safely stops the mock Society", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Build the cast. Let them talk." }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Game mode" })).toBeVisible();
  await page.locator(".mode-picker button", { hasText: "Society" }).click();
  await expect(page.locator(".mode-picker button", { hasText: "Society" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByRole("button", { name: /Live Society · Mock/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByText(/Ollama (checking|unavailable|connected)/)).toBeVisible();
  await expect(page.getByLabel("Population size")).toHaveValue("3");

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

  await page.getByRole("button", { name: "History & replay" }).click();
  const completedRun = page.locator(".history-run", { hasText: "completed" });
  await completedRun.click();
  await expect(page.getByText(/Replay verified for/)).toBeVisible();
  await expect(page.getByLabel(/Tick .* event/)).toBeVisible();
  const baseline = await completedRun.locator("strong").innerText();
  const candidate = await page
    .getByLabel("Candidate run")
    .locator("option")
    .evaluateAll((options, selected) =>
      options.map((option) => (option as HTMLOptionElement).value).find(
        (value) => value && value !== selected,
      ), baseline);
  if (!candidate) throw new Error("Expected a second run for comparison");
  await page.getByLabel("Candidate run").selectOption(candidate);
  await page.getByRole("button", { name: "Compare outcomes" }).click();
  await expect(page.getByText("Comparison ready")).toBeVisible();
});

test("randomizes and edits a population before preview", async ({ page }) => {
  await page.goto("/");
  await page.locator(".mode-picker button", { hasText: "Society" }).click();
  await expect(page.getByLabel("Population size")).toHaveValue("3");
  await page.getByLabel("Population size").fill("2");
  await page.getByRole("button", { name: "Randomize population" }).click();
  await expect(page.getByLabel("Agent ID").first()).toHaveValue("agent-1");
  const generatedName = await page.getByLabel("Display name").first().inputValue();
  await page.getByRole("button", { name: "Resolve & preview agents" }).click();
  await expect(page.getByText("2 active agents · seed 97")).toBeVisible();
  await expect(
    page.locator(".agent-panel").getByText(generatedName, { exact: true }),
  ).toBeVisible();
});

test("configures and previews a randomized local-model conversation", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".mode-picker button", { hasText: "Conversation" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: /Local AI Conversation/ })).toHaveAttribute("aria-pressed", "true");
  await page.getByLabel("Conversation preset").selectOption("dinner");
  await expect(page.getByLabel("Topic")).toHaveValue(/ambition or contentment/);
  await page.getByLabel("Population size").fill("2");
  await page.getByRole("button", { name: "Randomize population" }).click();
  await expect(page.getByText("Secret motives / private information").first()).toBeVisible();
  await page.getByRole("button", { name: "Preview configuration" }).click();
  await expect(page.getByText(/2 active agents/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Start simulation/ })).toBeVisible();
});

test("edits, validates, previews, and runs a custom definition", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Custom builder" }).click();

  await expect(
    page.getByRole("heading", { name: "Define the rules. Run the world." }),
  ).toBeVisible();
  await page.getByLabel("Simulation description").fill(
    "Workers process a queue of warehouse orders.",
  );
  await page.getByRole("button", { name: "Generate editable proposal" }).click();
  await expect(page.getByText(/proposal inserted/)).toBeVisible();
  await page.getByLabel("run.ticks").fill("1");
  await page.getByRole("button", { name: "Validate & preview" }).click();
  await expect(page.getByText("worker-a", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /Run custom simulation/ }).click();
  await expect(page.locator(".custom-results .status")).toHaveText("completed");
  await expect(page.locator(".custom-results .feed li")).toHaveCount(2);
  await expect(page.locator(".custom-results .state-panel pre")).toContainText(
    '"orders_remaining": 5',
  );
});
