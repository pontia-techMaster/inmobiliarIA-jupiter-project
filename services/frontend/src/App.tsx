import { useState, type FormEvent } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TRACER_URL = import.meta.env.VITE_TRACER_URL ?? "http://localhost:9000";

type Status =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "submitted"; requestId: string }
  | { kind: "error"; message: string };

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;

    setStatus({ kind: "submitting" });
    try {
      const res = await fetch(`${API_URL}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: { request_id: string } = await res.json();
      setStatus({ kind: "submitted", requestId: data.request_id });
    } catch (err) {
      setStatus({
        kind: "error",
        message: err instanceof Error ? err.message : "Error desconocido",
      });
    }
  }

  function reset() {
    setPrompt("");
    setStatus({ kind: "idle" });
  }

  return (
    <main className="container">
      <header>
        <h1>InmobiliarIA</h1>
        <p className="tagline">Búsqueda inmobiliaria por lenguaje natural</p>
      </header>

      <form onSubmit={onSubmit}>
        <label htmlFor="prompt">¿Qué tipo de vivienda buscas?</label>
        <textarea
          id="prompt"
          rows={4}
          placeholder="Ej.: Piso luminoso de 3 habitaciones en el Barrio de Salamanca, con ascensor y exterior."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={status.kind === "submitting" || status.kind === "submitted"}
        />
        <button
          type="submit"
          disabled={
            !prompt.trim() ||
            status.kind === "submitting" ||
            status.kind === "submitted"
          }
        >
          {status.kind === "submitting" ? "Enviando…" : "Buscar"}
        </button>
      </form>

      {status.kind === "submitted" && (
        <section className="status status--ok">
          <p>Su petición está siendo procesada</p>
          <small>id: {status.requestId}</small>
          <div className="status-actions">
            <a
              className="link"
              href={`${TRACER_URL}/?id=${status.requestId}`}
              target="_blank"
              rel="noreferrer"
            >
              Ver traza →
            </a>
            <button type="button" className="link" onClick={reset}>
              Nueva búsqueda
            </button>
          </div>
        </section>
      )}

      {status.kind === "error" && (
        <section className="status status--err">
          <p>No se pudo enviar la petición.</p>
          <small>{status.message}</small>
          <button type="button" className="link" onClick={reset}>
            Reintentar
          </button>
        </section>
      )}
    </main>
  );
}
