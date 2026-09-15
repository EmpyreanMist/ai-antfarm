export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export type Scenario = {
  id: string;
  mode: string;
  name: string;
  description: string;
  runtime: "mock" | "ollama";
  featured: boolean;
  agent_count: number;
  default_active_agents: number;
  seed: number;
  ticks: number;
  environment: string;
  models: string[];
  durable: boolean;
};

export type ScenarioTemplate = Pick<
  Scenario,
  "id" | "name" | "description" | "runtime" | "featured"
>;

export type GameMode = {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  configuration_hints: Record<string, JsonValue>;
  visualization_hints: Record<string, JsonValue>;
  templates: ScenarioTemplate[];
};

export type Agent = {
  agent_id: string;
  model_ref: string;
  model: string;
  configuration: Record<string, JsonValue>;
  public: Record<string, JsonValue>;
};

export type Resolution = {
  resolution_id: string;
  scenario_id: string;
  mode: string;
  run_id: string;
  seed: number;
  ticks: number;
  active_agent_count: number;
  runtime_overrides: Record<string, JsonValue>;
  agents: Agent[];
};

export type RunState = {
  run_id: string;
  mode: "bounded" | "continuous";
  status: "running" | "stopping" | "completed" | "stopped" | "failed";
  tick: number;
  failure: string | null;
};

export type SimulationEvent = {
  schema_version: number;
  event_id: string;
  run_id: string;
  sequence: number;
  tick: number;
  kind: string;
  actor_id: string | null;
  causation_id: string | null;
  payload: Record<string, JsonValue>;
};

export type Snapshot = {
  run_id: string;
  tick: number;
  world: Record<string, JsonValue>;
  metrics: Record<string, JsonValue>;
};

export type CustomDefinition = Record<string, JsonValue> & {
  schema_version: number;
  kind: "custom";
  run: { id: string; seed: number; ticks: number };
};

export type CustomEntity = {
  entity_id: string;
  entity_type: string;
  behavior: string | null;
  configuration: Record<string, JsonValue>;
  public: Record<string, JsonValue>;
};

export type CustomPreview = {
  definition: CustomDefinition;
  entities: CustomEntity[];
};

export type CustomResolution = CustomPreview & {
  resolution_id: string;
  kind: "custom";
  run_id: string;
  seed: number;
  ticks: number;
  runtime_overrides: Record<string, JsonValue>;
};

export type GeneratedCustom = {
  definition: CustomDefinition;
  provenance: {
    kind: string;
    generator: string;
    description_length: number;
    schema_version: number;
  };
};

export type ResolveInput = {
  seed?: number;
  run_id?: string;
  active_agents?: number;
  model?: string;
  profiles?: Record<string, Record<string, JsonValue>>;
  model_assignments?: Record<string, string>;
};

export type StartInput = {
  resolution_id: string;
  mode: "bounded" | "continuous";
  tick_seconds: number;
};

const API_URL = (
  process.env.NEXT_PUBLIC_ANTFARM_API_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

export async function listModes(): Promise<GameMode[]> {
  const response = await request<{ items: GameMode[] }>("/modes");
  return response.items;
}

export async function listModeScenarios(modeId: string): Promise<Scenario[]> {
  const response = await request<{ items: Scenario[] }>(
    `/modes/${encodeURIComponent(modeId)}/scenarios`,
  );
  return response.items;
}

export function resolveScenario(
  scenarioId: string,
  input: ResolveInput,
): Promise<Resolution> {
  return request(`/scenarios/${encodeURIComponent(scenarioId)}/resolve`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getCustomStarter(): Promise<CustomDefinition> {
  return request("/custom/starter");
}

export function validateCustom(
  definition: CustomDefinition,
): Promise<CustomPreview> {
  return request("/custom/validate", {
    method: "POST",
    body: JSON.stringify(definition),
  });
}

export function resolveCustom(
  definition: CustomDefinition,
): Promise<CustomResolution> {
  return request("/custom/resolve", {
    method: "POST",
    body: JSON.stringify({ definition }),
  });
}

export function generateCustom(description: string): Promise<GeneratedCustom> {
  return request("/custom/generate", {
    method: "POST",
    body: JSON.stringify({ description }),
  });
}

export function startRun(input: StartInput): Promise<RunState> {
  return request("/runs", { method: "POST", body: JSON.stringify(input) });
}

export function stopRun(runId: string): Promise<RunState> {
  return request(`/runs/${encodeURIComponent(runId)}/stop`, { method: "POST" });
}

export async function inspectRun(runId: string): Promise<{
  agents: Agent[];
  snapshot: Snapshot | null;
}> {
  const encoded = encodeURIComponent(runId);
  const [agentPage, snapshot] = await Promise.all([
    request<{ items: Agent[] }>(`/runs/${encoded}/agents?limit=1000`),
    request<Snapshot | null>(`/runs/${encoded}/snapshot`),
  ]);
  return { agents: agentPage.items, snapshot };
}

export async function inspectCustomRun(runId: string): Promise<{
  entities: CustomEntity[];
  snapshot: Snapshot | null;
}> {
  const encoded = encodeURIComponent(runId);
  const [entityPage, snapshot] = await Promise.all([
    request<{ items: CustomEntity[] }>(`/runs/${encoded}/entities?limit=1000`),
    request<Snapshot | null>(`/runs/${encoded}/snapshot`),
  ]);
  return { entities: entityPage.items, snapshot };
}

export function eventStreamUrl(runId: string, after: number): string {
  const url = new URL(`${API_URL}/runs/${encodeURIComponent(runId)}/events/stream`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("after", String(after));
  url.searchParams.set(
    "kinds",
    [
      "action.applied",
      "action.noop",
      "action.rejected",
      "cognition.failed",
      "cognition.malformed",
      "cognition.timed_out",
    ].join(","),
  );
  return url.toString();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}
