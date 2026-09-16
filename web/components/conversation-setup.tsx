"use client";

import type { ConversationSettings } from "@/lib/api";

type Preset = ConversationSettings & { id: string; name: string };

export const CONVERSATION_PRESETS: Preset[] = [
  { id: "open", name: "Open conversation", topic: "What question is most worth discussing right now?", situation: "The participants meet for the first time and may take the conversation anywhere useful.", turns: 12, memory_limit: 20 },
  { id: "dinner", name: "Dinner party", topic: "Should ambition or contentment guide a good life?", situation: "A dinner party has become unusually candid. The guests disagree but must remain at the table together.", turns: 16, memory_limit: 24 },
  { id: "debate", name: "Heated debate", topic: "Does powerful AI create more freedom or more control?", situation: "A live debate is underway. Each participant wants to persuade the room and must address prior arguments.", turns: 18, memory_limit: 30 },
  { id: "negotiation", name: "Hostile negotiation", topic: "How should a scarce shared resource be divided?", situation: "The parties distrust one another, time is running out, and no agreement means everyone loses.", turns: 20, memory_limit: 32 },
  { id: "philosophy", name: "Philosophical discussion", topic: "Can a person be free if their choices are predictable?", situation: "A late-night discussion among thoughtful strangers. They should challenge assumptions and build on earlier ideas.", turns: 18, memory_limit: 30 },
  { id: "jury", name: "Jury deliberation", topic: "Is the available evidence enough to reach a confident verdict?", situation: "A jury must reach a decision. Evidence is incomplete, personalities clash, and every juror has a private concern.", turns: 24, memory_limit: 40 },
  { id: "stranded", name: "Stranded group", topic: "What should the group do during the next 24 hours?", situation: "The participants are stranded after a disaster with limited supplies and conflicting priorities.", turns: 20, memory_limit: 32 },
  { id: "factions", name: "Rival factions", topic: "Can two rival groups create a stable truce?", situation: "Representatives of rival factions meet in secret. Old grievances remain and both sides fear appearing weak.", turns: 22, memory_limit: 36 },
  { id: "planning", name: "Team planning", topic: "What is the strongest plan for achieving an apparently impossible goal?", situation: "A diverse team has one meeting to produce a concrete plan, expose risks, and assign priorities.", turns: 16, memory_limit: 28 },
];

export const DEFAULT_CONVERSATION: ConversationSettings = settings(CONVERSATION_PRESETS[0]);

type Props = {
  value: ConversationSettings;
  onChange: (value: ConversationSettings) => void;
  onRandomAll: () => void;
};

export function ConversationSetup({ value, onChange, onRandomAll }: Props) {
  const selected = CONVERSATION_PRESETS.find(
    (preset) => preset.topic === value.topic && preset.situation === value.situation,
  );

  function choosePreset(id: string) {
    const preset = CONVERSATION_PRESETS.find((item) => item.id === id);
    if (preset) onChange(settings(preset));
  }

  function surprise() {
    const values = new Uint32Array(1);
    crypto.getRandomValues(values);
    const preset = CONVERSATION_PRESETS[values[0] % CONVERSATION_PRESETS.length];
    onChange(settings(preset));
    onRandomAll();
  }

  return (
    <section className="conversation-setup wide">
      <div className="conversation-heading">
        <div><p className="eyebrow">Step 1 · Set the scene</p><h3>What should they talk about?</h3><small>Characters are instructed to stay inside this topic, situation, and their configured profiles.</small></div>
        <button type="button" className="surprise" onClick={surprise}>✦ Random all</button>
      </div>
      <div className="conversation-fields">
        <div className="preset-grid wide" role="radiogroup" aria-label="Conversation preset">{CONVERSATION_PRESETS.map((preset) => <button type="button" role="radio" aria-checked={selected?.id === preset.id} key={preset.id} onClick={() => choosePreset(preset.id)}>{preset.name}</button>)}</div>
        <label className="wide">Topic<input value={value.topic} onChange={(event) => onChange({ ...value, topic: event.target.value })} /></label>
        <label className="wide">Situation / opening context<textarea rows={3} value={value.situation} onChange={(event) => onChange({ ...value, situation: event.target.value })} /></label>
        <details className="conversation-advanced wide"><summary>Conversation length and memory</summary><div><label>Number of turns<input type="number" min="1" max="100" value={value.turns} onChange={(event) => onChange({ ...value, turns: Number(event.target.value) })} /></label><label>Remember recent messages<input type="number" min="1" max="100" value={value.memory_limit} onChange={(event) => onChange({ ...value, memory_limit: Number(event.target.value) })} /></label></div></details>
      </div>
    </section>
  );
}

function settings(preset: Preset): ConversationSettings {
  return {
    topic: preset.topic,
    situation: preset.situation,
    turns: preset.turns,
    memory_limit: preset.memory_limit,
  };
}
