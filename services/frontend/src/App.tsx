import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
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

const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 90;          // 90 × 2s = 3 min upper bound

const USER_ID_KEY = "inmo.user_id";

function getOrCreateUserId(): string {
  try {
    const existing = localStorage.getItem(USER_ID_KEY);
    if (existing) return existing;
    const fresh = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, fresh);
    return fresh;
  } catch {
    return crypto.randomUUID();
  }
}

type HistoryItem = {
  user_id: string;
  request_id: string;
  created_at: number;
  prompt: string;
  result: SearchResult | null;
};

type Property = {
  id: string | number;
  price: number | null;
  property_type: string | null;
  property_subtype: string | null;
  street: string | null;
  neighborhood: string | null;
  district: string | null;
  rooms: number | null;
  bathrooms: number | null;
  surface: number | null;
  floor: string | null;
  is_exterior: boolean | null;
  has_elevator: boolean | null;
  images: string[] | null;
  url: string | null;
  description: string | null;
  score: number | null;
};

type SearchResult = {
  request_id: string;
  results: Property[];
};

type Status =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "polling"; requestId: string; attempt: number }
  | { kind: "done"; requestId: string; data: SearchResult }
  | { kind: "timeout"; requestId: string }
  | { kind: "error"; message: string };

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const userId = useMemo(getOrCreateUserId, []);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // Selected result ids (per-property, not per-request). Cleared on reset
  // and on history navigation since the underlying results change.
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  const refetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/users/${userId}/searches`);
      if (!res.ok) return;
      const body: { searches: HistoryItem[] } = await res.json();
      setHistory(body.searches ?? []);
    } catch {
      // History is best-effort; silent failure is fine.
    }
  }, [userId]);

  useEffect(() => {
    refetchHistory();
  }, [refetchHistory]);

  useEffect(() => {
    if (status.kind === "done") refetchHistory();
  }, [status, refetchHistory]);

  useEffect(() => {
    if (status.kind !== "polling") return;
    const { requestId, attempt } = status;

    let cancelled = false;
    const nextPoll = () => {
      if (attempt + 1 >= POLL_MAX_ATTEMPTS) {
        setStatus({ kind: "timeout", requestId });
      } else {
        setStatus({ kind: "polling", requestId, attempt: attempt + 1 });
      }
    };

    const timer = setTimeout(async () => {
      if (cancelled) return;
      try {
        const res = await fetch(`${API_URL}/results/${requestId}`);
        if (cancelled) return;
        if (res.ok) {
          const data: SearchResult = await res.json();
          setStatus({ kind: "done", requestId, data });
          return;
        }
        nextPoll();
      } catch {
        if (!cancelled) nextPoll();
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [status]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;

    setStatus({ kind: "submitting" });
    setSelected(new Set());
    const requestId = crypto.randomUUID();
    try {
      const res = await fetch(`${API_URL}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: requestId, prompt, user_id: userId }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStatus({ kind: "polling", requestId, attempt: 0 });
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
    setSelected(new Set());
  }

  function loadFromHistory(item: HistoryItem) {
    if (!item.result) return;
    setPrompt(item.prompt);
    setStatus({ kind: "done", requestId: item.request_id, data: item.result });
    setSelected(new Set());
  }

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll(props: Property[]) {
    setSelected(new Set(props.map((p) => String(p.id))));
  }

  function clearSelection() {
    setSelected(new Set());
  }

  function generatePdf() {
    // Tag <html> so the print stylesheet hides non-selected cards.
    // Using window.print() lets the user pick "Save as PDF" in the system
    // print dialog — no extra dependency, faithful HTML rendering.
    document.documentElement.classList.add("printing-selection");
    const cleanup = () => {
      document.documentElement.classList.remove("printing-selection");
      window.removeEventListener("afterprint", cleanup);
    };
    window.addEventListener("afterprint", cleanup);
    // Safari doesn't always fire afterprint; remove on a timer too.
    setTimeout(cleanup, 1000);
    window.print();
  }

  const requestId =
    status.kind === "polling" || status.kind === "done" || status.kind === "timeout"
      ? status.requestId
      : null;

  const results = status.kind === "done" ? status.data.results : [];
  const selectedCount = selected.size;

  return (
    <main className="container">
      <header className="brand">
        <h1>InmobiliarIA</h1>
        <p className="tagline">Búsqueda inmobiliaria por lenguaje natural</p>
      </header>

      <form onSubmit={onSubmit}>
        <label htmlFor="prompt">¿Qué tipo de vivienda buscas?</label>
        <textarea
          id="prompt"
          rows={3}
          placeholder="Ej.: Piso luminoso de 3 habitaciones en el Barrio de Salamanca, con ascensor y exterior."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={status.kind === "submitting"}
        />
        <button type="submit" disabled={!prompt.trim() || status.kind === "submitting"}>
          {status.kind === "submitting" ? "Enviando…" : "Buscar"}
        </button>
      </form>

      {history.length > 0 && (
        <HistoryPanel items={history} activeRequestId={requestId} onPick={loadFromHistory} />
      )}

      {status.kind === "polling" && (
        <section className="status status--polling">
          <p>
            Buscando<span className="dots" />
            <small className="attempt">
              {" "}({status.attempt + 1}/{POLL_MAX_ATTEMPTS})
            </small>
          </p>
          {requestId && <RequestIdRow id={requestId} />}
          <ul className="result-list" aria-hidden="true">
            <ResultSkeleton />
            <ResultSkeleton />
            <ResultSkeleton />
          </ul>
        </section>
      )}

      {status.kind === "timeout" && (
        <section className="status status--err">
          <p>La búsqueda tarda más de lo previsto.</p>
          <small>
            Sigue procesándose en segundo plano. Refresca dentro de unos minutos o intenta otra
            búsqueda.
          </small>
          {requestId && <RequestIdRow id={requestId} />}
          <button type="button" className="link" onClick={reset}>
            Nueva búsqueda
          </button>
        </section>
      )}

      {status.kind === "done" && (
        <section className="results">
          <header className="results-header">
            <h2>
              {results.length === 0
                ? "Sin resultados"
                : `${results.length} ${results.length === 1 ? "resultado" : "resultados"}`}
            </h2>
            <div className="results-actions">
              {results.length > 0 && (
                <>
                  {selectedCount === 0 ? (
                    <button type="button" className="btn-secondary" onClick={() => selectAll(results)}>
                      Seleccionar todo
                    </button>
                  ) : (
                    <button type="button" className="btn-secondary" onClick={clearSelection}>
                      Limpiar selección ({selectedCount})
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={generatePdf}
                    disabled={selectedCount === 0}
                    title={
                      selectedCount === 0
                        ? "Selecciona al menos un resultado"
                        : `Generar PDF con ${selectedCount} resultado${selectedCount === 1 ? "" : "s"}`
                    }
                  >
                    Generar PDF{selectedCount > 0 ? ` (${selectedCount})` : ""}
                  </button>
                </>
              )}
              <button type="button" className="btn-secondary" onClick={reset}>
                Volver a buscar
              </button>
            </div>
          </header>
          {requestId && <RequestIdRow id={requestId} />}
          {results.length === 0 ? (
            <EmptyState onReset={reset} />
          ) : (
            <ul className="result-list">
              {results.map((p, i) => {
                const id = String(p.id ?? i);
                return (
                  <ResultCard
                    key={id}
                    property={p}
                    selected={selected.has(id)}
                    onToggle={() => toggleSelected(id)}
                  />
                );
              })}
            </ul>
          )}
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

// ──────────────────────────────────────────────────────────────────────────────
// History panel: sticky, horizontal pills
// ──────────────────────────────────────────────────────────────────────────────

function HistoryPanel({
  items,
  activeRequestId,
  onPick,
}: {
  items: HistoryItem[];
  activeRequestId: string | null;
  onPick: (item: HistoryItem) => void;
}) {
  return (
    <section className="history">
      <div className="history-label">
        <span>Tus búsquedas</span>
        <small>{items.length}</small>
      </div>
      <ul className="history-list">
        {items.map((item) => {
          const isActive = item.request_id === activeRequestId;
          const count = item.result?.results?.length ?? 0;
          return (
            <li key={item.request_id}>
              <button
                type="button"
                className={`history-pill ${isActive ? "history-pill--active" : ""}`}
                onClick={() => onPick(item)}
                disabled={!item.result}
                title={item.prompt}
              >
                <span className="history-prompt">{item.prompt || "(sin prompt)"}</span>
                <span className="history-meta">
                  {count} · {formatRelative(item.created_at)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function formatRelative(epochSeconds: number): string {
  const diffSec = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  if (diffSec < 60) return "ahora";
  const min = Math.floor(diffSec / 60);
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d} d`;
  return new Date(epochSeconds * 1000).toLocaleDateString("es-ES");
}

function RequestIdRow({ id }: { id: string }) {
  return (
    <div className="id-row">
      <small>id: {id}</small>
      <button
        type="button"
        className="link link--mini"
        onClick={() => navigator.clipboard?.writeText(id)}
        title="Copiar al portapapeles"
      >
        Copiar
      </button>
      {IS_CLOUD ? (
        <a
          className="link link--mini"
          href={CW_INSIGHTS_URL}
          target="_blank"
          rel="noreferrer"
          title="Filtra los logs por este id en CloudWatch Logs Insights"
        >
          Ver en CloudWatch ↗
        </a>
      ) : (
        <a className="link link--mini" href={`${TRACER_URL}/?id=${id}`} target="_blank" rel="noreferrer">
          Ver traza →
        </a>
      )}
    </div>
  );
}

function ResultSkeleton() {
  return (
    <li className="result-card skeleton">
      <div className="result-image">
        <div className="skeleton-block" />
      </div>
      <div className="result-body">
        <div className="skeleton-line skeleton-line--title" />
        <div className="skeleton-line" />
        <div className="skeleton-line short" />
      </div>
    </li>
  );
}

function EmptyState({ onReset }: { onReset: () => void }) {
  return (
    <div className="empty-state">
      <p>No hemos encontrado propiedades que coincidan con tu búsqueda.</p>
      <small>Prueba a relajar los filtros (zona, número de habitaciones, precio…).</small>
      <button type="button" className="link" onClick={onReset}>
        Nueva búsqueda
      </button>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Result card
// ──────────────────────────────────────────────────────────────────────────────

const PROPERTY_TYPE_LABELS: Record<string, string> = {
  apartment: "Piso",
  house: "Casa",
};

const SUBTYPE_LABELS: Record<string, string> = {
  flat: "Piso",
  penthouse: "Ático",
  duplex: "Dúplex",
  studio: "Estudio",
  apartment: "Apartamento",
  chalet: "Chalet",
  villa: "Villa",
  townhouse: "Adosado",
  detached_house: "Unifamiliar",
  house: "Casa",
};

function ResultCard({
  property: p,
  selected,
  onToggle,
}: {
  property: Property;
  selected: boolean;
  onToggle: () => void;
}) {
  const typeLabel =
    (p.property_subtype && SUBTYPE_LABELS[p.property_subtype]) ??
    (p.property_type && PROPERTY_TYPE_LABELS[p.property_type]) ??
    "Propiedad";

  const locationLine = [p.neighborhood, p.district].filter(Boolean).join(" · ");

  const specs: string[] = [];
  if (p.rooms != null) specs.push(`${p.rooms} hab.`);
  if (p.bathrooms != null) specs.push(`${p.bathrooms} ${p.bathrooms === 1 ? "baño" : "baños"}`);
  if (p.surface != null) specs.push(`${p.surface} m²`);
  if (p.floor) specs.push(`Planta ${p.floor}`);

  const badges: { label: string; tone?: "ok" | "muted" }[] = [];
  if (p.is_exterior === true) badges.push({ label: "Exterior", tone: "ok" });
  if (p.is_exterior === false) badges.push({ label: "Interior", tone: "muted" });
  if (p.has_elevator === true) badges.push({ label: "Ascensor", tone: "ok" });

  const images = p.images ?? [];

  return (
    <li
      className={`result-card ${selected ? "result-card--selected" : ""}`}
      data-selected={selected}
    >
      <label className="result-checkbox" title={selected ? "Deseleccionar" : "Seleccionar"}>
        <input type="checkbox" checked={selected} onChange={onToggle} />
        <span aria-hidden="true" />
      </label>

      <div className="result-image">
        {images.length > 0 ? (
          <Carousel
            images={images}
            alt={`${typeLabel}${locationLine ? ` en ${locationLine}` : ""}`}
          />
        ) : (
          <div className="result-image-placeholder" aria-hidden="true">
            🏠
          </div>
        )}
        {p.score != null && (
          <span className="score-badge" title="Puntuación de relevancia">
            Score: {p.score.toFixed(2)}
          </span>
        )}
      </div>

      <div className="result-body">
        <h3>
          {typeLabel}
          {locationLine && <span className="result-location"> · {locationLine}</span>}
        </h3>
        {p.street && <p className="result-street">{p.street}</p>}

        {specs.length > 0 && <p className="result-meta">{specs.join(" · ")}</p>}

        {badges.length > 0 && (
          <div className="result-badges">
            {badges.map((b) => (
              <span key={b.label} className={`badge badge--${b.tone ?? "default"}`}>
                {b.label}
              </span>
            ))}
          </div>
        )}

        {p.description && <p className="result-desc">{p.description}</p>}

        <div className="result-footer">
          {p.price != null ? (
            <span className="result-price">{Number(p.price).toLocaleString("es-ES")} €</span>
          ) : (
            <span className="result-price result-price--missing">Precio no disponible</span>
          )}
          {p.url && (
            <a href={p.url} target="_blank" rel="noreferrer" className="link">
              Ver anuncio ↗
            </a>
          )}
        </div>
      </div>
    </li>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Image carousel
// ──────────────────────────────────────────────────────────────────────────────

function Carousel({ images, alt }: { images: string[]; alt: string }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);

  const goTo = useCallback(
    (next: number) => {
      const total = images.length;
      const wrapped = ((next % total) + total) % total;
      setIndex(wrapped);
      const el = trackRef.current;
      if (el) {
        el.scrollTo({ left: wrapped * el.clientWidth, behavior: "smooth" });
      }
    },
    [images.length],
  );

  // Track index when the user swipes the carousel manually.
  function onScroll() {
    const el = trackRef.current;
    if (!el) return;
    const i = Math.round(el.scrollLeft / el.clientWidth);
    if (i !== index) setIndex(i);
  }

  if (images.length === 0) return null;
  const showControls = images.length > 1;

  return (
    <div className="carousel" aria-roledescription="carousel">
      <div className="carousel-track" ref={trackRef} onScroll={onScroll}>
        {images.map((src, i) => (
          <img
            key={src}
            src={src}
            alt={`${alt} (foto ${i + 1}/${images.length})`}
            loading={i === 0 ? "eager" : "lazy"}
            draggable={false}
          />
        ))}
      </div>
      {showControls && (
        <>
          <button
            type="button"
            className="carousel-btn carousel-btn--prev"
            onClick={(e) => {
              e.stopPropagation();
              goTo(index - 1);
            }}
            aria-label="Foto anterior"
          >
            ‹
          </button>
          <button
            type="button"
            className="carousel-btn carousel-btn--next"
            onClick={(e) => {
              e.stopPropagation();
              goTo(index + 1);
            }}
            aria-label="Siguiente foto"
          >
            ›
          </button>
          <div className="carousel-counter" aria-live="polite">
            {index + 1} / {images.length}
          </div>
        </>
      )}
    </div>
  );
}
