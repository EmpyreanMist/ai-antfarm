"use client";

import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";

import {
  CustomDefinition,
  CustomEntity,
  CustomPreview,
  eventStreamUrl,
  getCustomStarter,
  inspectCustomRun,
  JsonValue,
  resolveCustom,
  RunState,
  SimulationEvent,
  Snapshot,
  startRun,
  stopRun,
  validateCustom,
} from "@/lib/api";

const DRAFT_KEY = "antfarm.custom-definition.v1";
const TERMINAL = new Set(["completed", "stopped", "failed"]);

export function CustomBuilder() {
  const [definition, setDefinition] = useState<CustomDefinition | null>(null);
  const [preview, setPreview] = useState<CustomPreview | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [entities, setEntities] = useState<CustomEntity[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lastSequence = useRef(0);
  const terminalRun = useRef(false);

  const loadStarter = useCallback(async (preferDraft: boolean) => {
    setBusy(true);
    setError("");
    try {
      const starter = await getCustomStarter();
      if (preferDraft) {
        const saved = window.localStorage.getItem(DRAFT_KEY);
        if (saved) {
          const parsed = JSON.parse(saved) as CustomDefinition;
          setDefinition(parsed);
          return;
        }
      }
      setDefinition(starter);
      setPreview(null);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadStarter(true);
  }, [loadStarter]);

  useEffect(() => {
    if (definition) {
      window.localStorage.setItem(DRAFT_KEY, JSON.stringify(definition));
    }
  }, [definition]);

  const refreshInspection = useCallback(async (runId: string) => {
    const inspection = await inspectCustomRun(runId);
    setEntities(inspection.entities);
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
        } else if (data.type === "state") {
          terminalRun.current = TERMINAL.has(data.state.status);
          setRun(data.state);
          void refreshInspection(data.state.run_id).catch((reason: unknown) => {
            setError(errorMessage(reason));
          });
        } else {
          lastSequence.current = data.after;
        }
      };
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

  async function validate() {
    if (!definition) return;
    setBusy(true);
    setError("");
    try {
      const result = await validateCustom(definition);
      setDefinition(result.definition);
      setPreview(result);
      setEntities(result.entities);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function launch() {
    if (!definition) return;
    setBusy(true);
    setError("");
    try {
      const resolved = await resolveCustom(definition);
      const state = await startRun({
        resolution_id: resolved.resolution_id,
        mode: "bounded",
        tick_seconds: 1,
      });
      setPreview(resolved);
      setRun(state);
      setEvents([]);
      setSnapshot(null);
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

  function update(path: PathPart[], value: JsonValue) {
    if (!definition) return;
    setDefinition(setAtPath(definition, path, value) as CustomDefinition);
    setPreview(null);
  }

  function importDefinition(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    void file.text().then((text) => {
      try {
        setDefinition(JSON.parse(text) as CustomDefinition);
        setPreview(null);
        setError("");
      } catch {
        setError("Imported file is not valid JSON.");
      }
    });
    event.target.value = "";
  }

  function exportDefinition() {
    if (!definition) return;
    const blob = new Blob([JSON.stringify(definition, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${definition.run.id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="shell custom-shell">
      <header className="hero compact-hero">
        <div>
          <p className="eyebrow">AntFarm / custom simulation builder</p>
          <h1>Define the rules.<br />Run the world.</h1>
          <p className="lede">Structured authoring over the same validated M7 definition used by Python callers.</p>
        </div>
        <div className="boundary-note"><span className="pulse" />Data only<small>No imported or executable code</small></div>
      </header>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}

      <div className="builder-toolbar">
        <button type="button" onClick={() => void loadStarter(false)}>Reset starter</button>
        <label className="file-button">Import JSON<input type="file" accept="application/json,.json" onChange={importDefinition} /></label>
        <button type="button" onClick={exportDefinition} disabled={!definition}>Export JSON</button>
        <span>Draft saved locally</span>
      </div>

      {definition ? (
        <section className="builder-layout">
          <div className="definition-editor">
            <EditorSection title="Run" value={definition.run} path={["run"]} onChange={update} />
            <EditorSection title="World fields" value={definition.world_fields} path={["world_fields"]} onChange={update} />
            <EditorSection title="World state" value={definition.world_state} path={["world_state"]} onChange={update} />
            <EditorSection title="Entity types" value={definition.entity_types} path={["entity_types"]} onChange={update} />
            <EditorSection title="Entities" value={definition.entities} path={["entities"]} onChange={update} />
            <EditorSection title="Actions" value={definition.actions} path={["actions"]} onChange={update} />
            <EditorSection title="Observations" value={definition.observations} path={["observations"]} onChange={update} />
            <EditorSection title="Activation" value={definition.activation} path={["activation"]} onChange={update} />
            <EditorSection title="Termination" value={definition.termination} path={["termination"]} onChange={update} />
            <EditorSection title="Storage" value={definition.storage} path={["storage"]} onChange={update} />
          </div>
          <aside className="builder-side">
            <div className="builder-actions">
              <button className="primary" type="button" onClick={validate} disabled={busy}>Validate & preview</button>
              <button className="launch" type="button" onClick={launch} disabled={busy || !preview}>Run custom simulation <span>→</span></button>
            </div>
            <div className="panel custom-preview">
              <div className="panel-title"><h3>Resolved entities</h3><span>{entities.length}</span></div>
              {entities.map((entity) => <article key={entity.entity_id}><strong>{entity.entity_id}</strong><small>{entity.entity_type} · {entity.behavior ?? "inert"}</small><pre>{JSON.stringify(entity.public, null, 2)}</pre></article>)}
            </div>
          </aside>
        </section>
      ) : <div className="empty"><p>{busy ? "Loading starter…" : "No custom definition loaded."}</p></div>}

      <section className="custom-results">
        <div className="run-strip">
          <div><small>Status</small><strong className={`status ${run?.status ?? "idle"}`}>{run?.status ?? "idle"}</strong></div>
          <div><small>Run</small><strong>{run?.run_id ?? "Not started"}</strong></div>
          <div><small>Tick</small><strong>{run?.tick ?? 0}</strong></div>
          {run && !TERMINAL.has(run.status) ? <button type="button" className="stop" onClick={stop}>Stop safely</button> : null}
        </div>
        <div className="monitor-grid">
          <div className="feed panel"><div className="panel-title"><h3>Committed events</h3><span>{events.length}</span></div><ol>{events.toReversed().map((event) => <li key={event.event_id}><span>t{event.tick}</span><div><strong>{event.actor_id ?? "system"}</strong><p>{event.kind} · {String(event.payload.kind ?? "")}</p></div><em>#{event.sequence}</em></li>)}</ol></div>
          <div className="panel state-panel"><div className="panel-title"><h3>Custom state</h3><span>tick {snapshot?.tick ?? 0}</span></div>{snapshot ? <pre>{JSON.stringify(snapshot.world, null, 2)}</pre> : <div className="empty"><p>Run the definition to inspect state.</p></div>}</div>
        </div>
      </section>
    </main>
  );
}

type PathPart = string | number;
type ChangeHandler = (path: PathPart[], value: JsonValue) => void;

function EditorSection({ title, value, path, onChange }: { title: string; value: JsonValue; path: PathPart[]; onChange: ChangeHandler }) {
  return <section className="editor-section"><h2>{title}</h2><StructuredNode label={title} value={value} path={path} onChange={onChange} /></section>;
}

function StructuredNode({ label, value, path, onChange }: { label: string; value: JsonValue; path: PathPart[]; onChange: ChangeHandler }) {
  const [newKey, setNewKey] = useState("");
  if (Array.isArray(value)) {
    return <div className="array-editor">{value.map((item, index) => <div className="array-item" key={index}><StructuredNode label={`${label} ${index + 1}`} value={item} path={[...path, index]} onChange={onChange} /><div className="row-tools"><button type="button" onClick={() => onChange(path, value.filter((_, itemIndex) => itemIndex !== index))}>Remove</button><button type="button" onClick={() => onChange(path, [...value.slice(0, index + 1), structuredClone(item), ...value.slice(index + 1)])}>Duplicate</button></div></div>)}</div>;
  }
  if (isObject(value)) {
    const entries = Object.entries(value);
    return <div className="object-editor">{entries.map(([key, item]) => <details key={key} open={path.length < 2 || !isComplex(item)}><summary>{humanize(key)}</summary><StructuredNode label={key} value={item} path={[...path, key]} onChange={onChange} /><button className="delete-value" type="button" onClick={() => onChange(path, withoutKey(value, key))}>Remove {humanize(key)}</button></details>)}<div className="add-value"><input aria-label={`New key in ${path.join(".")}`} value={newKey} onChange={(event) => setNewKey(event.target.value)} placeholder="new_key" /><button type="button" disabled={!newKey} onClick={() => { onChange(path, { ...value, [newKey]: "" }); setNewKey(""); }}>Add value</button><button type="button" disabled={!newKey || entries.length === 0} onClick={() => { onChange(path, { ...value, [newKey]: structuredClone(entries[0][1]) }); setNewKey(""); }}>Duplicate template</button></div></div>;
  }
  const options = selectOptions(path.at(-1));
  if (typeof value === "boolean") {
    return <label className="scalar-field"><span>{humanize(label)}</span><input aria-label={path.join(".")} type="checkbox" checked={value} onChange={(event) => onChange(path, event.target.checked)} /></label>;
  }
  if (options) {
    return <label className="scalar-field"><span>{humanize(label)}</span><select aria-label={path.join(".")} value={String(value ?? "")} onChange={(event) => onChange(path, event.target.value)}>{options.map((option) => <option key={option}>{option}</option>)}</select></label>;
  }
  return <label className="scalar-field"><span>{humanize(label)}</span><input aria-label={path.join(".")} type={typeof value === "number" ? "number" : "text"} value={value == null ? "" : String(value)} onChange={(event) => onChange(path, typeof value === "number" ? Number(event.target.value) : event.target.value)} /></label>;
}

function setAtPath(root: JsonValue, path: PathPart[], value: JsonValue): JsonValue {
  if (path.length === 0) return value;
  const clone = structuredClone(root);
  let cursor = clone as Record<string | number, JsonValue>;
  for (const part of path.slice(0, -1)) cursor = cursor[part] as Record<string | number, JsonValue>;
  cursor[path.at(-1)!] = value;
  return clone;
}

function withoutKey(value: Record<string, JsonValue>, key: string): Record<string, JsonValue> {
  return Object.fromEntries(Object.entries(value).filter(([name]) => name !== key));
}

function isObject(value: JsonValue): value is Record<string, JsonValue> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isComplex(value: JsonValue): boolean { return Array.isArray(value) || isObject(value); }
function humanize(value: string): string { return value.replaceAll("_", " "); }
function errorMessage(reason: unknown): string { return reason instanceof Error ? reason.message : "An unexpected error occurred."; }

function selectOptions(key: PathPart | undefined): string[] | null {
  if (key === "type") return ["integer", "number", "string", "boolean", "array", "object"];
  if (key === "visibility") return ["public", "owner", "internal"];
  if (key === "operator") return ["eq", "not_eq", "gte", "lte"];
  if (key === "operation") return ["set", "add"];
  if (key === "scope") return ["world", "actor"];
  if (key === "source") return ["literal", "parameter"];
  return null;
}

type StreamMessage =
  | { type: "event"; event: SimulationEvent }
  | { type: "state"; state: RunState }
  | { type: "recovery_required"; after: number; reason: string };
