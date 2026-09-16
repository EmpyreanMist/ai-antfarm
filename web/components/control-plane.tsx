"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { AgentBuilder } from "@/components/agent-builder";
import {
  ConversationSetup,
  DEFAULT_CONVERSATION,
} from "@/components/conversation-setup";

import {
  Agent,
  AgentDraft,
  ConversationSettings,
  eventStreamUrl,
  GameMode,
  inspectRun,
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
  const [runId, setRunId] = useState("");
  const [agentDrafts, setAgentDrafts] = useState<AgentDraft[]>([]);
  const [mode, setMode] = useState<"bounded" | "continuous">("bounded");
  const [tickSeconds, setTickSeconds] = useState("1");
  const [conversation, setConversation] = useState<ConversationSettings>(DEFAULT_CONVERSATION);
  const [randomizeNonce, setRandomizeNonce] = useState(0);
  const lastSequence = useRef(0);
  const terminalRun = useRef(false);

  const selected = scenarios.find((scenario) => scenario.id === selectedId);
  const selectedMode = modes.find((item) => item.id === selectedModeId);
  const isConversation = selectedModeId === "conversation";

  useEffect(() => {
    let active = true;
    listModes()
      .then((items) => {
        if (!active) return;
        setModes(items);
        const preferred = items.find((item) => item.id === "conversation") ?? items[0];
        if (preferred) setSelectedModeId(preferred.id);
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
    setRunId("");
    setAgentDrafts([]);
    setResolution(null);
    setRun(null);
    setEvents([]);
    setAgents([]);
    setSnapshot(null);
    setRandomizeNonce(0);
    lastSequence.current = 0;
    terminalRun.current = true;
  }, [selected]);

  const receiveAgentDrafts = useCallback((drafts: AgentDraft[]) => {
    setAgentDrafts(drafts);
    setResolution(null);
  }, []);

  const receiveBuilderError = useCallback((message: string) => {
    setError(message);
  }, []);

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
      const resolved = await resolveScenario(selected.id, {
        seed: numberOrUndefined(seed),
        run_id: runId.trim() || undefined,
        agents: agentDrafts,
        conversation: isConversation ? conversation : undefined,
      });
      setResolution(resolved);
      setAgents(resolved.agents);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function startConversation() {
    if (!selected || agentDrafts.length === 0) return;
    setBusy(true);
    setError("");
    try {
      const resolved = await resolveScenario(selected.id, {
        seed: numberOrUndefined(seed),
        run_id: runId.trim() || undefined,
        agents: agentDrafts,
        conversation,
      });
      setAgents(resolved.agents);
      const state = await startRun({
        resolution_id: resolved.resolution_id,
        mode: "bounded",
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

  function randomizeEverything() {
    const values = new Uint32Array(1);
    crypto.getRandomValues(values);
    setSeed(String(values[0]));
    setRandomizeNonce((current) => current + 1);
    setResolution(null);
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
          <p className="eyebrow">AntFarm / local AI social sandbox</p>
          <h1>Build the cast.<br />Let them talk.</h1>
          <p className="lede">
            Choose local models, shape every personality, set the situation,
            and watch autonomous characters react to one another.
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
            <label className="wide">Run ID <span>optional</span><input value={runId} onChange={(event) => setRunId(event.target.value)} placeholder="generated automatically" /></label>
            {isConversation ? <ConversationSetup value={conversation} onChange={(value) => { setConversation(value); setResolution(null); }} onRandomAll={randomizeEverything} /> : null}
            {selected ? <AgentBuilder
              key={`${selected.id}-${randomizeNonce}`}
              scenarioId={selected.id}
              runtime={selected.runtime}
              configuredModels={selected.models}
              initialCount={selected.default_active_agents}
              seed={numberOrUndefined(seed) ?? selected.seed}
              autoRandomize={isConversation && randomizeNonce > 0}
              onChange={receiveAgentDrafts}
              onError={receiveBuilderError}
            /> : null}
            {isConversation ? <>
              <button className="preview-button" disabled={busy || !selected || agentDrafts.length === 0} type="submit">Preview configuration</button>
              <button className="primary" disabled={busy || !selected || agentDrafts.length === 0} type="button" onClick={() => void startConversation()}>{busy ? "Starting…" : "Start conversation →"}</button>
            </> : <button className="primary wide" disabled={busy || !selected || agentDrafts.length === 0} type="submit">{busy ? "Resolving…" : "Resolve & preview agents"}</button>}
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
          <div><p>Observe</p><h2>{isConversation ? "Live conversation" : "Live committed activity"}</h2></div>
        </div>
        <div className="run-strip">
          <div><small>Status</small><strong className={`status ${run?.status ?? "idle"}`}>{run?.status ?? "idle"}</strong></div>
          <div><small>Run</small><strong>{run?.run_id ?? "No active run"}</strong></div>
          <div><small>Tick</small><strong>{run?.tick ?? 0}</strong></div>
          {run && !TERMINAL.has(run.status) ? <button type="button" className="stop" disabled={busy} onClick={stop}>Stop safely</button> : null}
        </div>
        <div className="monitor-grid">
          <div className="feed panel">
            <div className="panel-title"><h3>{isConversation ? "Conversation" : "Event feed"}</h3><span>{events.length} shown</span></div>
            {events.length === 0 ? <Empty label="Committed speech and actions will appear here." /> : (
              <ol>{[...events].reverse().map((event) => <li key={event.event_id}><span>t{event.tick}</span><div><strong>{actorName(event.actor_id, agents)}</strong><p>{formatEvent(event)}</p></div><em>#{event.sequence}</em></li>)}</ol>
            )}
          </div>
          <div className="inspectors">
            <div className="panel agent-panel">
              <div className="panel-title"><h3>Agents</h3><span>{agents.length}</span></div>
              {agents.length === 0 ? <Empty label="Resolve a scenario to inspect its agents." /> : <div className="agent-grid">{agents.map((agent) => <article key={agent.agent_id}><span>{initials(agent)}</span><div><strong>{displayName(agent)}</strong><small>{agent.model}</small><details><summary>Resolved public/private preview</summary><h4>Public</h4><pre>{JSON.stringify(agent.public, null, 2)}</pre><h4>Complete configuration</h4><pre>{JSON.stringify(agent.configuration, null, 2)}</pre></details></div></article>)}</div>}
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

function actorName(actorId: string | null, agents: Agent[]): string {
  if (actorId === null) return "system";
  const agent = agents.find((item) => item.agent_id === actorId);
  return agent ? displayName(agent) : actorId.replaceAll("-", " ");
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
