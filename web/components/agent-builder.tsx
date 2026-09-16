"use client";

import { useEffect, useState } from "react";

import {
  discoverLocalModels,
  generateAgentDrafts,
  getAgentDrafts,
  type AgentDraft,
  type JsonValue,
  type LocalModels,
} from "@/lib/api";

const TRAITS = [
  "generosity", "greed", "selfishness", "empathy", "assertiveness",
  "agreeableness", "honesty", "conformity", "patience", "impulsiveness",
  "risk_tolerance", "competitiveness", "envy", "aggression", "trust",
  "ambition", "materialism", "fairness", "forgiveness", "sociability",
] as const;
const VISIBILITY = [
  "wealth", "possessions", "occupation", "status", "reputation",
  "relationships", "health", "group_membership",
] as const;

type Props = {
  scenarioId: string;
  runtime: "mock" | "ollama";
  configuredModels: string[];
  initialCount: number;
  seed: number;
  onChange: (agents: AgentDraft[]) => void;
  onError: (message: string) => void;
};

export function AgentBuilder({
  scenarioId,
  runtime,
  configuredModels,
  initialCount,
  seed,
  onChange,
  onError,
}: Props) {
  const [agents, setAgents] = useState<AgentDraft[]>([]);
  const [baseline, setBaseline] = useState<AgentDraft[]>([]);
  const [inventory, setInventory] = useState<LocalModels | null>(null);
  const [authoring, setAuthoring] = useState<"manual" | "random" | "mixed">("manual");
  const [sharedModel, setSharedModel] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    getAgentDrafts(scenarioId)
      .then((drafts) => {
        if (!active) return;
        const selected = drafts.slice(0, initialCount).map((draft) => ({
          ...draft,
          model: runtime === "ollama" ? draft.model : null,
        }));
        setAgents(selected);
        setBaseline(selected);
        setSharedModel(configuredModels[0] ?? "");
        onChange(selected);
      })
      .catch((error: unknown) => onError(message(error)));
    discoverLocalModels()
      .then((models) => {
        if (!active) return;
        setInventory(models);
        if (runtime === "ollama" && models.models[0]) {
          setSharedModel(models.models[0]);
        }
      })
      .catch((error: unknown) => onError(message(error)));
    return () => { active = false; };
  }, [configuredModels, initialCount, onChange, onError, runtime, scenarioId]);

  function commit(next: AgentDraft[]) {
    setAgents(next);
    onChange(next);
  }

  const modelOptions =
    runtime === "ollama" && inventory?.models.length
      ? inventory.models
      : configuredModels;
  const missingModels =
    runtime === "ollama" && inventory?.connected
      ? configuredModels.filter((model) => !inventory.models.includes(model))
      : [];

  useEffect(() => {
    if (runtime !== "ollama" || !inventory?.connected || !inventory.models[0]) return;
    setAgents((current) => {
      if (current.every((agent) => agent.model && inventory.models.includes(agent.model))) return current;
      const next = current.map((agent) => ({
        ...agent,
        model: agent.model && inventory.models.includes(agent.model)
          ? agent.model
          : inventory.models[0],
      }));
      onChange(next);
      return next;
    });
  }, [inventory, onChange, runtime]);

  async function randomizeAll() {
    const model = sharedModel || modelOptions[0];
    if (!model) return;
    setBusy(true);
    try {
      const generated = await generateAgentDrafts(scenarioId, {
        count: agents.length || initialCount,
        seed,
        model,
      });
      commit(generated.map((draft) => ({
        ...draft,
        model: runtime === "ollama" ? draft.model : null,
      })));
      setAuthoring("random");
    } catch (error) {
      onError(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function randomizeOne(index: number) {
    const current = agents[index];
    const model = current.model || sharedModel || modelOptions[0];
    if (!model) return;
    setBusy(true);
    try {
      const [generated] = await generateAgentDrafts(scenarioId, {
        count: 1,
        seed: seed + index + 1,
        model,
      });
      const next = [...agents];
      next[index] = {
        ...generated,
        id: current.id,
        model: runtime === "ollama" ? model : null,
      };
      commit(next);
      setAuthoring("mixed");
    } catch (error) {
      onError(message(error));
    } finally {
      setBusy(false);
    }
  }

  function setPopulationSize(count: number) {
    const bounded = Math.max(1, Math.min(10, count));
    if (bounded <= agents.length) {
      commit(agents.slice(0, bounded));
      return;
    }
    const source = agents.at(-1) ?? baseline[0];
    if (!source) return;
    const next = [...agents];
    while (next.length < bounded) {
      next.push({
        ...structuredClone(source),
        id: uniqueId(source.id, next),
      });
    }
    commit(next);
  }

  function setAllModels(model: string) {
    setSharedModel(model);
    if (runtime === "ollama") {
      commit(agents.map((agent) => ({ ...agent, model })));
    }
  }

  return (
    <div className="agent-builder wide">
      <div className="builder-heading">
        <div><p className="eyebrow">Shared Agent Builder</p><h3>Population</h3></div>
          <div className={`runtime-state ${inventory?.connected ? "connected" : "offline"}`}>
          <span /> Ollama {inventory === null ? "checking" : inventory.connected ? "connected" : "unavailable"}
        </div>
      </div>
      <div className="builder-toolbar">
        <label>Authoring mode<select value={authoring} onChange={(event) => setAuthoring(event.target.value as typeof authoring)}><option value="manual">Manual</option><option value="random">Random</option><option value="mixed">Mixed</option></select></label>
        <label>Population size<input aria-label="Population size" type="number" min="1" max="10" value={agents.length || initialCount} onChange={(event) => setPopulationSize(Number(event.target.value))} /></label>
        <label>Shared model<select aria-label="Shared model" value={sharedModel} disabled={!modelOptions.length} onChange={(event) => setAllModels(event.target.value)}>{modelOptions.map((model) => <option key={model} value={model}>{model}</option>)}</select></label>
        <button type="button" disabled={busy || !modelOptions.length} onClick={() => void randomizeAll()}>Randomize population</button>
        <button type="button" disabled={!baseline.length} onClick={() => commit(baseline.map((agent) => structuredClone(agent)))}>Reset all</button>
      </div>
      {runtime === "ollama" && inventory?.connected && inventory.models.length === 0 ? <p className="builder-warning">Ollama is connected but has no installed models.</p> : null}
      {missingModels.length ? <p className="builder-warning">Missing configured models: {missingModels.join(", ")}. Choose an installed model below.</p> : null}
      <div className="agent-editor-list">
        {agents.map((agent, index) => (
          <AgentEditor
            key={`${agent.id}-${index}`}
            agent={agent}
            index={index}
            models={modelOptions}
            modelEnabled={runtime === "ollama"}
            busy={busy}
            onUpdate={(updated) => commit(agents.map((item, itemIndex) => itemIndex === index ? updated : item))}
            onRandomize={() => void randomizeOne(index)}
            onClone={() => agents.length < 10 && commit([...agents, { ...structuredClone(agent), id: uniqueId(agent.id, agents) }])}
            onReset={() => {
              const original = baseline.find((item) => item.id === agent.id);
              if (original) commit(agents.map((item, itemIndex) => itemIndex === index ? structuredClone(original) : item));
            }}
            onRemove={() => agents.length > 1 && commit(agents.filter((_, itemIndex) => itemIndex !== index))}
          />
        ))}
      </div>
    </div>
  );
}

type EditorProps = {
  agent: AgentDraft;
  index: number;
  models: string[];
  modelEnabled: boolean;
  busy: boolean;
  onUpdate: (agent: AgentDraft) => void;
  onRandomize: () => void;
  onClone: () => void;
  onReset: () => void;
  onRemove: () => void;
};

function AgentEditor({ agent, index, models, modelEnabled, busy, onUpdate, onRandomize, onClone, onReset, onRemove }: EditorProps) {
  function set(path: string[], value: JsonValue) {
    const profile = structuredClone(agent.profile);
    let cursor = profile as Record<string, JsonValue>;
    for (const key of path.slice(0, -1)) {
      const existing = cursor[key];
      if (!existing || typeof existing !== "object" || Array.isArray(existing)) cursor[key] = {};
      cursor = cursor[key] as Record<string, JsonValue>;
    }
    cursor[path.at(-1) ?? ""] = value;
    onUpdate({ ...agent, profile });
  }
  const text = (path: string[]) => stringAt(agent.profile, path);
  return <details className="agent-editor" open={index === 0}>
    <summary><strong>{text(["identity", "display_name"]) || agent.id}</strong><span>{agent.model ?? "scenario model"}</span></summary>
    <div className="agent-editor-fields">
      <label>Agent ID<input value={agent.id} onChange={(event) => onUpdate({ ...agent, id: event.target.value })} /></label>
      <label>Display name<input value={text(["identity", "display_name"])} onChange={(event) => set(["identity", "display_name"], event.target.value)} /></label>
      <label className="wide">Identity description<textarea rows={2} value={text(["identity", "description"])} onChange={(event) => set(["identity", "description"], event.target.value)} /></label>
      <label className="wide">Personality<textarea rows={2} value={text(["personality", "description"])} onChange={(event) => set(["personality", "description"], event.target.value)} /></label>
      <ListField label="Qualities" value={arrayAt(agent.profile, ["personality", "qualities"])} onChange={(value) => set(["personality", "qualities"], value)} />
      <ListField label="Goals" value={arrayAt(agent.profile, ["goals"])} onChange={(value) => set(["goals"], value)} />
      <ListField label="Beliefs" value={arrayAt(agent.profile, ["beliefs"])} onChange={(value) => set(["beliefs"], value)} />
      <ListField label="Values" value={arrayAt(agent.profile, ["values"])} onChange={(value) => set(["values"], value)} />
      <label>Communication style<input value={text(["communication_preferences", "style"])} onChange={(event) => set(["communication_preferences", "style"], event.target.value)} /></label>
      <ListField label="Communication preferences" value={arrayAt(agent.profile, ["communication_preferences", "preferences"])} onChange={(value) => set(["communication_preferences", "preferences"], value)} />
      {modelEnabled ? <label>Model<select value={agent.model ?? ""} onChange={(event) => onUpdate({ ...agent, model: event.target.value })}>{models.map((model) => <option key={model} value={model}>{model}</option>)}</select></label> : null}
      <label>Cognition interval<input type="number" min="1" value={agent.cognition_interval ?? ""} onChange={(event) => onUpdate({ ...agent, cognition_interval: event.target.value ? Number(event.target.value) : null })} /></label>
      <details className="wide trait-editor"><summary>Behavioral traits</summary><div>{TRAITS.map((trait) => <label key={trait}>{trait.replaceAll("_", " ")}<input type="range" min="0" max="1" step="0.01" value={numberAt(agent.profile, ["behavioral_traits", trait], .5)} onChange={(event) => set(["behavioral_traits", trait], Number(event.target.value))} /><output>{numberAt(agent.profile, ["behavioral_traits", trait], .5).toFixed(2)}</output></label>)}</div></details>
      <label>Money<input type="number" min="0" value={numberAt(agent.profile, ["economics", "money"], 0)} onChange={(event) => set(["economics", "money"], Number(event.target.value))} /></label>
      <label>Recurring income<input type="number" min="0" value={numberAt(agent.profile, ["economics", "recurring_income"], 0)} onChange={(event) => set(["economics", "recurring_income"], Number(event.target.value))} /></label>
      <label>Occupation<input value={text(["economics", "occupation"])} onChange={(event) => set(["economics", "occupation"], event.target.value)} /></label>
      <MapField label="Resources / items" value={objectAt(agent.profile, ["economics", "resources"])} onChange={(value) => set(["economics", "resources"], value)} />
      <label>Social status<input value={text(["social_status", "label"])} onChange={(event) => set(["social_status", "label"], event.target.value)} /></label>
      <ListField label="Social roles" value={arrayAt(agent.profile, ["social_status", "roles"])} onChange={(value) => set(["social_status", "roles"], value)} />
      <label>Reputation score<input type="range" min="0" max="1" step="0.01" value={numberAt(agent.profile, ["reputation", "score"], .5)} onChange={(event) => set(["reputation", "score"], Number(event.target.value))} /></label>
      <ListField label="Reputation labels" value={arrayAt(agent.profile, ["reputation", "labels"])} onChange={(value) => set(["reputation", "labels"], value)} />
      <RelationshipField value={objectAt(agent.profile, ["relationships"])} onChange={(value) => set(["relationships"], value)} />
      <details className="wide visibility-editor"><summary>Public / private visibility</summary><div>{VISIBILITY.map((field) => <label key={field}>{field.replaceAll("_", " ")}<select value={text(["visibility", field]) || "private"} onChange={(event) => set(["visibility", field], event.target.value)}><option value="private">Private</option><option value="public">Public</option></select></label>)}</div></details>
      <ListField label="Private information" value={arrayAt(agent.profile, ["private_information"])} onChange={(value) => set(["private_information"], value)} />
    </div>
    <div className="agent-actions"><button type="button" disabled={busy} onClick={onRandomize}>Randomize</button><button type="button" onClick={onClone}>Clone</button><button type="button" onClick={onReset}>Reset</button><button type="button" onClick={onRemove}>Remove</button></div>
  </details>;
}

function ListField({ label, value, onChange }: { label: string; value: string[]; onChange: (value: string[]) => void }) {
  return <label>{label}<textarea rows={2} value={value.join("\n")} onChange={(event) => onChange(event.target.value.split("\n").map((item) => item.trim()).filter(Boolean))} /></label>;
}

function MapField({ label, value, onChange }: { label: string; value: Record<string, JsonValue>; onChange: (value: Record<string, JsonValue>) => void }) {
  const lines = Object.entries(value).map(([key, item]) => `${key}=${String(item)}`).join("\n");
  return <label>{label}<textarea rows={2} value={lines} placeholder="food=2" onChange={(event) => {
    const next: Record<string, JsonValue> = {};
    for (const line of event.target.value.split("\n")) {
      const [key, raw] = line.split("=", 2).map((item) => item.trim());
      if (key && raw && Number.isInteger(Number(raw)) && Number(raw) >= 0) next[key] = Number(raw);
    }
    onChange(next);
  }} /></label>;
}

function RelationshipField({ value, onChange }: { value: Record<string, JsonValue>; onChange: (value: Record<string, JsonValue>) => void }) {
  const lines = Object.entries(value).map(([target, item]) => {
    const relation = item && typeof item === "object" && !Array.isArray(item) ? item : {};
    return `${target}, ${String(relation.kind ?? "acquaintance")}, ${String(relation.strength ?? .5)}`;
  }).join("\n");
  return <label className="wide">Relationships <span>target, kind, strength</span><textarea rows={2} value={lines} placeholder="alice, ally, 0.8" onChange={(event) => {
    const next: Record<string, JsonValue> = {};
    for (const line of event.target.value.split("\n")) {
      const [target, kind, rawStrength] = line.split(",").map((item) => item.trim());
      const strength = Number(rawStrength);
      if (target && kind && Number.isFinite(strength) && strength >= 0 && strength <= 1) next[target] = { kind, strength };
    }
    onChange(next);
  }} /></label>;
}

function valueAt(profile: Record<string, JsonValue>, path: string[]): JsonValue | undefined {
  let value: JsonValue | undefined = profile;
  for (const key of path) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
    value = value[key];
  }
  return value;
}

function stringAt(profile: Record<string, JsonValue>, path: string[]): string {
  const value = valueAt(profile, path);
  return typeof value === "string" ? value : "";
}

function arrayAt(profile: Record<string, JsonValue>, path: string[]): string[] {
  const value = valueAt(profile, path);
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function objectAt(profile: Record<string, JsonValue>, path: string[]): Record<string, JsonValue> {
  const value = valueAt(profile, path);
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function numberAt(profile: Record<string, JsonValue>, path: string[], fallback: number): number {
  const value = valueAt(profile, path);
  return typeof value === "number" ? value : fallback;
}

function uniqueId(base: string, agents: AgentDraft[]): string {
  const taken = new Set(agents.map((agent) => agent.id));
  let suffix = 2;
  let candidate = `${base}-${suffix}`;
  while (taken.has(candidate)) candidate = `${base}-${++suffix}`;
  return candidate;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Agent Builder failed.";
}
