"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import {
  Agent,
  eventStreamUrl,
  GameMode,
  inspectRun,
  JsonValue,
  listModes,
  listModeScenarios,
  Resolution,
  resolveScenario,
  RunState,
  Scenario,
  SimulationEvent,
  Snapshot,
  startRun,
  stopRun,
} from "@/lib/api";

const TERMINAL = new Set(["completed", "stopped", "failed"]);

export function ControlPlane() {
  const [modes, setModes] = useState<GameMode[]>([]);
  const [selectedModeId, setSelectedModeId] = useState("");
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [resolution, setResolution] = useState<Resolution | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [seed, setSeed] = useState("");
  const [activeAgents, setActiveAgents] = useState("");
  const [runId, setRunId] = useState("");
  const [model, setModel] = useState("");
  const [profileOverrides, setProfileOverrides] = useState("{}");
  const [modelAssignments, setModelAssignments] = useState("{}");
  const [mode, setMode] = useState<"bounded" | "continuous">("bounded");
  const [tickSeconds, setTickSeconds] = useState("1");
  const lastSequence = useRef(0);
  const terminalRun = useRef(false);

  const selected = scenarios.find((scenario) => scenario.id === selectedId);
  const selectedMode = modes.find((item) => item.id === selectedModeId);

  useEffect(() => {
    let active = true;
    listModes()
      .then((items) => {
        if (!active) return;
        setModes(items);
        if (items[0]) setSelectedModeId(items[0].id);
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedModeId) return;
    let active = true;
    listModeScenarios(selectedModeId)
      .then((items) => {
        if (!active) return;
        setScenarios(items);
        const featured = items.find((item) => item.featured) ?? items[0];
        setSelectedId(featured?.id ?? "");
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [selectedModeId]);

  useEffect(() => {
    if (!selected) return;
    setSeed(String(selected.seed));
    setActiveAgents(String(selected.default_active_agents));
    setRunId("");
    setModel("");
    setResolution(null);
    setRun(null);
    setEvents([]);
    setAgents([]);
    setSnapshot(null);
    lastSequence.current = 0;
    terminalRun.current = true;
  }, [selected]);

  const refreshInspection = useCallback(async (id: string) => {
    const inspection = await inspectRun(id);
    setAgents(inspection.agents);
    setSnapshot(inspection.snapshot);
  }, []);

  useEffect(() => {
    if (!run) return;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      socket = new WebSocket(eventStreamUrl(run.run_id, lastSequence.current));
      socket.onmessage = (message) => {
        const data = JSON.parse(String(message.data)) as StreamMessage;
        if (data.type === "event") {
          lastSequence.current = Math.max(lastSequence.current, data.event.sequence);
          setEvents((current) => [...current.slice(-199), data.event]);
          return;
        }
        if (data.type === "state") {
          terminalRun.current = TERMINAL.has(data.state.status);
          setRun(data.state);
          void refreshInspection(data.state.run_id).catch((reason: unknown) => {
            setError(errorMessage(reason));
          });
          return;
        }
        if (data.type === "recovery_required") {
          lastSequence.current = data.after;
        }
      };
      socket.onerror = () => setError("Live connection interrupted; reconnecting.");
      socket.onclose = () => {
        if (!cancelled && !terminalRun.current) {
          reconnectTimer = setTimeout(connect, 500);
        }
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [refreshInspection, run?.run_id]);

  async function preview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const profiles = parseObject(profileOverrides, "Profile overrides");
      const assignments = parseStringMap(modelAssignments, "Model assignments");
      const resolved = await resolveScenario(selected.id, {
        seed: numberOrUndefined(seed),
        active_agents: numberOrUndefined(activeAgents),
        run_id: runId.trim() || undefined,
        model: model.trim() || undefined,
        profiles,
        model_assignments: assignments,
      });
      setResolution(resolved);
      setAgents(resolved.agents);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    if (!resolution) return;
    setBusy(true);
    setError("");
    try {
      const state = await startRun({
        resolution_id: resolution.resolution_id,
        mode,
        tick_seconds: Number(tickSeconds),
      });
      setRun(state);
      setEvents([]);
      setResolution(null);
      lastSequence.current = 0;
      terminalRun.current = false;
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    if (!run) return;
    setBusy(true);
    setError("");
    try {
      const state = await stopRun(run.run_id);
      terminalRun.current = true;
      setRun(state);
      await refreshInspection(state.run_id);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">AntFarm / minimum web control plane</p>
          <h1>Run a society.<br />Watch it become.</h1>
          <p className="lede">
            Choose a game mode, resolve its agents, and observe
            only events committed by the authoritative simulation server.
          </p>
        </div>
        <div className="boundary-note">
          <span className="pulse" />
          Server authoritative
          <small>UI → API → application → engine</small>
        </div>
      </header>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}

      <section className="workspace">
        <aside className="scenario-column">
          <div className="section-heading">
            <span>01</span>
            <div><p>Choose</p><h2>Game mode</h2></div>
          </div>
          <div className="mode-picker">
            {modes.map((item) => (
              <button
                type="button"
                key={item.id}
                aria-pressed={selectedModeId === item.id}
                onClick={() => setSelectedModeId(item.id)}
              >
                <strong>{item.name}</strong>
                <span>{item.description}</span>
              </button>
            ))}
          </div>
          <div className="mode-capabilities">
            {selectedMode?.capabilities.map((capability) => (
              <span key={capability}>{capability.replaceAll("_", " ")}</span>
            ))}
          </div>
          <h3 className="scenario-label">Scenario templates</h3>
          <div className="scenario-list">
            {scenarios.map((scenario) => (
              <button
                type="button"
                key={scenario.id}
                className={`scenario-card ${selectedId === scenario.id ? "selected" : ""}`}
                aria-pressed={selectedId === scenario.id}
                onClick={() => setSelectedId(scenario.id)}
              >
                <span className="scenario-topline">
                  <strong>{scenario.name}</strong>
                  <em>{scenario.runtime}</em>
                </span>
                <span>{scenario.description}</span>
                <small>{scenario.agent_count} agents · {scenario.ticks} configured ticks</small>
              </button>
            ))}
          </div>
        </aside>

        <section className="control-column">
          <div className="section-heading">
            <span>02</span>
            <div><p>Configure</p><h2>Resolve before running</h2></div>
          </div>
          <form className="config-form" onSubmit={preview}>
            <label>Seed<input value={seed} onChange={(event) => setSeed(event.target.value)} type="number" /></label>
            <label>Active agents<input value={activeAgents} onChange={(event) => setActiveAgents(event.target.value)} min="1" max={selected?.agent_count} type="number" /></label>
            <label className="wide">Run ID <span>optional</span><input value={runId} onChange={(event) => setRunId(event.target.value)} placeholder="generated automatically" /></label>
            <label className="wide">Model override <span>optional</span><input value={model} onChange={(event) => setModel(event.target.value)} placeholder={selected?.models.join(", ")} /></label>
            <details className="wide advanced">
              <summary>Advanced overrides</summary>
              <label>Profile overrides <span>JSON by agent ID</span><textarea value={profileOverrides} onChange={(event) => setProfileOverrides(event.target.value)} rows={4} /></label>
              <label>Model assignments <span>JSON by agent ID</span><textarea value={modelAssignments} onChange={(event) => setModelAssignments(event.target.value)} rows={3} /></label>
            </details>
            <button className="primary wide" disabled={busy || !selected} type="submit">
              {busy ? "Resolving…" : "Resolve & preview agents"}
            </button>
          </form>

          {resolution ? (
            <div className="launch-panel">
              <div><p className="eyebrow">Resolved configuration</p><strong>{resolution.run_id}</strong><small>{resolution.active_agent_count} active agents · seed {resolution.seed}</small></div>
              <label>Run mode<select value={mode} onChange={(event) => setMode(event.target.value as "bounded" | "continuous")}><option value="bounded">Bounded</option><option value="continuous">Continuous</option></select></label>
              <label>Tick pace<input value={tickSeconds} min="0.05" step="0.05" onChange={(event) => setTickSeconds(event.target.value)} type="number" /></label>
              <button type="button" className="launch" disabled={busy} onClick={start}>Start simulation <span>→</span></button>
            </div>
          ) : null}
        </section>
      </section>

      <section className="monitor">
        <div className="section-heading">
          <span>03</span>
          <div><p>Observe</p><h2>Live committed activity</h2></div>
        </div>
        <div className="run-strip">
          <div><small>Status</small><strong className={`status ${run?.status ?? "idle"}`}>{run?.status ?? "idle"}</strong></div>
          <div><small>Run</small><strong>{run?.run_id ?? "No active run"}</strong></div>
          <div><small>Tick</small><strong>{run?.tick ?? 0}</strong></div>
          {run && !TERMINAL.has(run.status) ? <button type="button" className="stop" disabled={busy} onClick={stop}>Stop safely</button> : null}
        </div>
        <div className="monitor-grid">
          <div className="feed panel">
            <div className="panel-title"><h3>Event feed</h3><span>{events.length} shown</span></div>
            {events.length === 0 ? <Empty label="Committed speech and actions will appear here." /> : (
              <ol>{[...events].reverse().map((event) => <li key={event.event_id}><span>t{event.tick}</span><div><strong>{event.actor_id ?? "system"}</strong><p>{formatEvent(event)}</p></div><em>#{event.sequence}</em></li>)}</ol>
            )}
          </div>
          <div className="inspectors">
            <div className="panel agent-panel">
              <div className="panel-title"><h3>Agents</h3><span>{agents.length}</span></div>
              {agents.length === 0 ? <Empty label="Resolve a scenario to inspect its agents." /> : <div className="agent-grid">{agents.map((agent) => <article key={agent.agent_id}><span>{initials(agent)}</span><div><strong>{displayName(agent)}</strong><small>{agent.model}</small></div></article>)}</div>}
            </div>
            <div className="panel state-panel">
              <div className="panel-title"><h3>World state</h3><span>tick {snapshot?.tick ?? 0}</span></div>
              {snapshot ? <pre>{JSON.stringify(snapshot.world, null, 2)}</pre> : <Empty label="The latest atomic snapshot will appear here." />}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function Empty({ label }: { label: string }) {
  return <div className="empty"><span>◇</span><p>{label}</p></div>;
}

type StreamMessage =
  | { type: "event"; event: SimulationEvent }
  | { type: "state"; state: RunState }
  | { type: "recovery_required"; after: number; reason: string };

function parseObject(value: string, label: string): Record<string, Record<string, JsonValue>> {
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed as Record<string, Record<string, JsonValue>>;
}

function parseStringMap(value: string, label: string): Record<string, string> {
  const parsed = parseObject(value, label);
  if (Object.values(parsed).some((item) => typeof item !== "string")) {
    throw new Error(`${label} values must be strings.`);
  }
  return parsed as unknown as Record<string, string>;
}

function numberOrUndefined(value: string): number | undefined {
  return value.trim() ? Number(value) : undefined;
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "An unexpected error occurred.";
}

function displayName(agent: Agent): string {
  const identity = agent.public.identity;
  if (identity && typeof identity === "object" && !Array.isArray(identity)) {
    const name = identity.display_name;
    if (typeof name === "string") return name;
  }
  return agent.agent_id.replaceAll("-", " ");
}

function initials(agent: Agent): string {
  return displayName(agent).split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function formatEvent(event: SimulationEvent): string {
  const kind = event.payload.kind;
  if (event.kind === "action.applied" && kind === "say") {
    const message = event.payload.message;
    if (message && typeof message === "object" && !Array.isArray(message) && typeof message.text === "string") return `“${message.text}”`;
  }
  if (event.kind === "action.applied") return `${String(kind ?? "action")} applied`;
  if (event.kind === "action.rejected") return `${String(kind ?? "action")} rejected — ${String(event.payload.reason ?? "invalid")}`;
  if (event.kind === "action.noop") return "No action taken";
  return `${event.kind.replace("cognition.", "Cognition ")} — ${String(event.payload.reason ?? "unknown")}`;
}
