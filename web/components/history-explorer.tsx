"use client";

import { useEffect, useState } from "react";

import {
  compareRuns,
  listRuns,
  replayRun,
  type ReplayPage,
  type RunComparison,
  type RunHistoryItem,
} from "@/lib/api";

export function HistoryExplorer() {
  const [runs, setRuns] = useState<RunHistoryItem[]>([]);
  const [selected, setSelected] = useState("");
  const [candidate, setCandidate] = useState("");
  const [replay, setReplay] = useState<ReplayPage | null>(null);
  const [frame, setFrame] = useState(0);
  const [comparison, setComparison] = useState<RunComparison | null>(null);
  const [message, setMessage] = useState("Loading run history…");

  async function refresh() {
    try {
      const items = await listRuns();
      setRuns(items);
      setSelected((current) => current || items[0]?.run_id || "");
      setCandidate((current) => current || items[1]?.run_id || "");
      setMessage(items.length ? `${items.length} runs available` : "No runs yet");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "History failed");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function explore(runId: string) {
    setSelected(runId);
    setComparison(null);
    try {
      const result = await replayRun(runId);
      setReplay(result);
      setFrame(Math.max(0, result.items.length - 1));
      setMessage(`Replay verified for ${runId}`);
    } catch (error) {
      setReplay(null);
      setMessage(error instanceof Error ? error.message : "Replay failed");
    }
  }

  async function compare() {
    if (!selected || !candidate || selected === candidate) return;
    try {
      setComparison(await compareRuns(selected, candidate));
      setMessage("Comparison ready");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Comparison failed");
    }
  }

  const current = replay?.items[frame];
  return (
    <main className="history-workspace">
      <header className="hero compact-hero">
        <p className="eyebrow">M10 · Recorded evidence</p>
        <h1>Replay the world. Compare the outcome.</h1>
        <p>Replays use committed actions and checkpoints—never a model call.</p>
      </header>
      <section className="history-grid">
        <div className="panel">
          <div className="panel-heading">
            <h2>Run history</h2>
            <button type="button" onClick={() => void refresh()}>Refresh</button>
          </div>
          <p className="muted">{message}</p>
          <ul className="history-list">
            {runs.map((run) => (
              <li key={run.run_id}>
                <button
                  className="history-run"
                  type="button"
                  aria-pressed={selected === run.run_id}
                  onClick={() => void explore(run.run_id)}
                >
                  <strong>{run.run_id}</strong>
                  <span>{run.kind} · {run.status} · tick {run.tick}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel replay-panel">
          <h2>Verified replay</h2>
          {current ? (
            <>
              <label htmlFor="replay-frame">Tick {current.tick} · event {current.event_sequence}</label>
              <input
                id="replay-frame"
                type="range"
                min="0"
                max={Math.max(0, (replay?.items.length ?? 1) - 1)}
                value={frame}
                onChange={(event) => setFrame(Number(event.target.value))}
              />
              <div className="state-panel"><h3>World</h3><pre>{JSON.stringify(current.world, null, 2)}</pre></div>
              <div className="state-panel"><h3>Metrics</h3><pre>{JSON.stringify(current.metrics, null, 2)}</pre></div>
            </>
          ) : <p className="muted">Choose a run to reconstruct its timeline.</p>}
        </div>
      </section>
      <section className="panel comparison-panel">
        <h2>Compare runs</h2>
        <select aria-label="Candidate run" value={candidate} onChange={(event) => setCandidate(event.target.value)}>
          <option value="">Choose candidate</option>
          {runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.run_id}</option>)}
        </select>
        <button type="button" disabled={!selected || !candidate || selected === candidate} onClick={() => void compare()}>Compare outcomes</button>
        {comparison && <div className="comparison-results">
          <p><strong>{comparison.compatible ? "Compatible" : "Incompatible"}</strong> · tick delta {comparison.tick_delta}</p>
          {comparison.incompatible_fields.length > 0 && <p>Incompatible: {comparison.incompatible_fields.join(", ")}</p>}
          <div className="state-panel"><h3>State deltas</h3><pre>{JSON.stringify(comparison.state_deltas, null, 2)}</pre></div>
          <div className="state-panel"><h3>Metric deltas</h3><pre>{JSON.stringify(comparison.metric_deltas, null, 2)}</pre></div>
        </div>}
      </section>
    </main>
  );
}
