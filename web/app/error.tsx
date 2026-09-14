"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="shell centered">
      <section className="panel error-panel">
        <p className="eyebrow">Control plane error</p>
        <h1>The interface could not continue.</h1>
        <p>Check that both development servers are running, then try again.</p>
        <button type="button" className="primary" onClick={reset}>
          Try again
        </button>
      </section>
    </main>
  );
}
