"use client";

import { useEffect, useMemo, useRef } from "react";

import type {
  Agent,
  ConversationSettings,
  RunState,
  SimulationEvent,
} from "@/lib/api";

type Props = {
  agents: Agent[];
  conversation: ConversationSettings;
  events: SimulationEvent[];
  run: RunState | null;
};

export function ConversationFeed({ agents, conversation, events, run }: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const agentsById = useMemo(
    () => new Map(agents.map((agent, index) => [agent.agent_id, { agent, index }])),
    [agents],
  );

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [events.length]);

  return (
    <section className="conversation-stage panel" aria-label="Live conversation">
      <header className="conversation-stage-header">
        <div>
          <p className="eyebrow">Current topic</p>
          <h3>{conversation.topic}</h3>
          <p>{conversation.situation}</p>
        </div>
        <span className={`conversation-live ${run?.status ?? "idle"}`}>
          <i /> {run?.status === "running" ? "Talking" : run?.status ?? "Ready"}
        </span>
      </header>
      <div className="conversation-messages" aria-live="polite" aria-relevant="additions text">
        {events.length === 0 ? (
          <div className="conversation-empty">
            <span>“</span>
            <strong>The room is ready.</strong>
            <p>Start the conversation and each character will respond to what was actually said before.</p>
          </div>
        ) : events.map((event) => {
          const speech = speechFrom(event);
          if (speech === null) {
            return <SystemLine key={event.event_id} event={event} />;
          }
          const entry = event.actor_id ? agentsById.get(event.actor_id) : undefined;
          const name = entry ? displayName(entry.agent) : event.actor_id ?? "System";
          const color = (entry?.index ?? 0) % 6;
          return (
            <article className={`message-bubble speaker-${color}`} key={event.event_id}>
              <div className="message-avatar" aria-hidden="true">{initials(name)}</div>
              <div className="message-content">
                <header><strong>{name}</strong><span>turn {event.tick}</span></header>
                <p>{speech}</p>
              </div>
            </article>
          );
        })}
        {run?.status === "running" ? (
          <div className="typing-indicator" aria-label="A character is thinking"><i /><i /><i /></div>
        ) : null}
        <div ref={endRef} />
      </div>
    </section>
  );
}

function SystemLine({ event }: { event: SimulationEvent }) {
  const message = event.kind === "action.noop"
    ? "A character chose not to speak this turn."
    : event.kind === "action.rejected"
      ? `A reply was rejected: ${String(event.payload.reason ?? "invalid reply")}`
      : `A reply failed: ${String(event.payload.reason ?? event.kind)}`;
  return <p className="conversation-system" role="status">{message}</p>;
}

function speechFrom(event: SimulationEvent): string | null {
  if (event.kind !== "action.applied" || event.payload.kind !== "say") return null;
  const message = event.payload.message;
  return message && typeof message === "object" && !Array.isArray(message)
    && typeof message.text === "string"
    ? message.text
    : null;
}

function displayName(agent: Agent): string {
  const identity = agent.public.identity;
  if (identity && typeof identity === "object" && !Array.isArray(identity)) {
    const name = identity.display_name;
    if (typeof name === "string") return name;
  }
  return agent.agent_id.replaceAll("-", " ");
}

function initials(name: string): string {
  return name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}
