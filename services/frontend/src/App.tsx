import { useState, type FormEvent } from "react";
import "./App.css";

// Trim trailing slash so we don't end up with `…/api//search` when joining.
const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
const TRACER_URL = (import.meta.env.VITE_TRACER_URL ?? "http://localhost:9000").replace(/\/+$/, "");

// In cloud the frontend stack sets VITE_TRACER_URL = VITE_API_URL because
// the local docker tracer doesn't exist there yet. Detect that and link
// to CloudWatch Logs Insights instead.
const IS_CLOUD = TRACER_URL === API_URL;
const CW_REGION = "eu-west-1";
const CW_INSIGHTS_URL =
  `https://${CW_REGION}.console.aws.amazon.com/cloudwatch/home?region=${CW_REGION}#logsV2:logs-insights`;

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
    // Mint the request_id here. In cloud the API Gateway → SQS service
    // integration forwards the body verbatim and returns SQS's XML — there's
    // no JSON body to read a server-generated id from. The id we send is
    // what the chain propagates and what shows up in CloudWatch logs.
    const requestId = crypto.randomUUID();
    try {
      const res = await fetch(`${API_URL}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: requestId, prompt }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStatus({ kind: "submitted", requestId });
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
          disabled={status.kind === "submitting"}
        />
        <button
          type="submit"
          disabled={
            !prompt.trim() ||
            status.kind === "submitting"
          }
        >
          {status.kind === "submitting" ? "Enviando…" : "Buscar"}
        </button>
      </form>

      {status.kind === "submitted" && (
        <section className="status status--ok">
          <p>Su petición está siendo procesada</p>
          <div className="id-row">
            <small>id: {status.requestId}</small>
            <button
              type="button"
              className="link"
              onClick={() => navigator.clipboard?.writeText(status.requestId)}
              title="Copiar al portapapeles"
            >
              Copiar
            </button>
          </div>
          <div className="status-actions">
            {IS_CLOUD ? (
              <a
                className="link"
                href={CW_INSIGHTS_URL}
                target="_blank"
                rel="noreferrer"
                title="Filtra los logs por este id en CloudWatch Logs Insights"
              >
                Ver en CloudWatch ↗
              </a>
            ) : (
              <a
                className="link"
                href={`${TRACER_URL}/?id=${status.requestId}`}
                target="_blank"
                rel="noreferrer"
              >
                Ver traza →
              </a>
            )}
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
