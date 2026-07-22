"use client";

import type { CSSProperties, ReactNode } from "react";

// Small design-system kit. Inline styles reference the tokens in globals.css so
// the whole app stays visually consistent without a CSS framework dependency.

// --- Card ------------------------------------------------------------------

export function Card({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      className="glass"
      style={{
        padding: "1.25rem",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
// --- Button ----------------------------------------------------------------

type ButtonProps = {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "danger";
  type?: "button" | "submit";
  disabled?: boolean;
  size?: "sm" | "md";
  style?: CSSProperties;
};

export function Button({
  children,
  onClick,
  variant = "primary",
  type = "button",
  disabled,
  size = "md",
  style,
}: ButtonProps) {
  const palette: Record<string, CSSProperties> = {
    primary: {
      background: "linear-gradient(180deg, var(--accent-hover), var(--accent))",
      color: "#1a1205",
      border: "1px solid transparent",
      boxShadow: "var(--glow-accent)",
    },
    ghost: { background: "var(--surface-2)", color: "var(--fg)", border: "1px solid var(--border-strong)" },
    danger: { background: "var(--danger-soft)", color: "var(--danger)", border: "1px solid transparent" },
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.4rem",
        padding: size === "sm" ? "0.35rem 0.65rem" : "0.55rem 0.9rem",
        fontSize: size === "sm" ? "0.8rem" : "0.875rem",
        fontWeight: 550,
        borderRadius: "var(--radius-sm)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        transition: "background 120ms ease, opacity 120ms ease",
        ...palette[variant],
        ...style,
      }}
    >
      {children}
    </button>
  );
}
// --- Inputs ----------------------------------------------------------------

const fieldStyle: CSSProperties = {
  width: "100%",
  padding: "0.55rem 0.7rem",
  background: "var(--surface-2)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-sm)",
  color: "var(--fg)",
  fontSize: "0.875rem",
  outline: "none",
};

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
      <span style={{ fontSize: "0.75rem", color: "var(--muted)", fontWeight: 550 }}>{label}</span>
      {children}
    </label>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} style={{ ...fieldStyle, ...props.style }} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} style={{ ...fieldStyle, resize: "vertical", ...props.style }} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} style={{ ...fieldStyle, ...props.style }} />;
}
// --- Badge ------------------------------------------------------------------

type Tone = "neutral" | "accent" | "success" | "warning" | "danger";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  const tones: Record<Tone, CSSProperties> = {
    neutral: { background: "var(--surface-3)", color: "var(--muted)" },
    accent: { background: "var(--accent-soft)", color: "var(--accent-hover)" },
    success: { background: "var(--success-soft)", color: "var(--success)" },
    warning: { background: "var(--warning-soft)", color: "var(--warning)" },
    danger: { background: "var(--danger-soft)", color: "var(--danger)" },
  };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "0.15rem 0.5rem",
        fontSize: "0.72rem",
        fontWeight: 600,
        borderRadius: "999px",
        textTransform: "capitalize",
        ...tones[tone],
      }}
    >
      {children}
    </span>
  );
}

// Maps common status/priority strings to a badge tone.
export function toneFor(value: string): Tone {
  switch (value) {
    case "done":
    case "released":
    case "ready":
    case "approved":
      return "success";
    case "in_progress":
    case "active":
    case "scheduled":
      return "accent";
    case "blocked":
    case "overdue":
    case "high":
      return "danger";
    case "pending":
    case "wip":
    case "planned":
    case "medium":
      return "warning";
    default:
      return "neutral";
  }
}
// --- Page scaffolding -------------------------------------------------------

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "1rem",
        marginBottom: "1.5rem",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
        <h1>{title}</h1>
        {subtitle && <p style={{ margin: 0, color: "var(--muted)" }}>{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <Card style={{ padding: "2.5rem 1.5rem", textAlign: "center" }}>
      <p style={{ margin: 0, fontWeight: 600 }}>{title}</p>
      {hint && <p style={{ margin: "0.4rem 0 0", color: "var(--muted)" }}>{hint}</p>}
    </Card>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <p style={{ color: "var(--muted)" }}>{label}</p>;
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p style={{ color: "var(--danger)", margin: "0.5rem 0" }}>
      {(error as Error).message ?? "Something went wrong"}
    </p>
  );
}
// --- Modal ------------------------------------------------------------------

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
        zIndex: 50,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 460,
          background: "var(--surface)",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow)",
          padding: "1.5rem",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "1.25rem",
          }}
        >
          <h2>{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--muted)",
              fontSize: "1.25rem",
              cursor: "pointer",
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.9rem" }}>{children}</div>
      </div>
    </div>
  );
}

// --- Space-theme primitives -------------------------------------------------

// Orbital logo mark: a sun with an orbiting body on a ring.
export function GravityMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <defs>
        <radialGradient id="markSun" cx="40%" cy="35%">
          <stop offset="0%" stopColor="#ffd08a" />
          <stop offset="60%" stopColor="#f5a524" />
          <stop offset="100%" stopColor="#7a3c00" />
        </radialGradient>
      </defs>
      <ellipse cx="20" cy="20" rx="18" ry="8" stroke="rgba(140,150,210,0.4)" transform="rotate(-30 20 20)" />
      <circle cx="20" cy="20" r="7" fill="url(#markSun)" />
      <circle cx="35" cy="12" r="2.4" fill="#38bdf8" />
    </svg>
  );
}

// The Gravity Score™ ring — an SVG progress gauge with a glowing accent arc.
export function ScoreGauge({
  score,
  size = 72,
  label,
}: {
  score: number;
  size?: number;
  label?: string;
}) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          style={{ filter: "drop-shadow(0 0 6px var(--accent))" }}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ fontFamily: "var(--font-display)", fontSize: size * 0.3, fontWeight: 600 }}>
          {Math.round(score)}
        </span>
        {label && (
          <span style={{ fontSize: "0.55rem", color: "var(--muted-2)", letterSpacing: "0.08em" }}>
            {label}
          </span>
        )}
      </div>
    </div>
  );
}

// A labeled thin progress bar (budget spend, completion, etc.).
export function ProgressBar({
  value,
  tone = "accent",
  height = 6,
}: {
  value: number;
  tone?: "accent" | "cyan" | "success" | "danger";
  height?: number;
}) {
  const color = {
    accent: "var(--accent)",
    cyan: "var(--cyan)",
    success: "var(--success)",
    danger: "var(--danger)",
  }[tone];
  return (
    <div
      style={{
        width: "100%",
        height,
        background: "var(--surface-3)",
        borderRadius: 999,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${Math.max(0, Math.min(100, value))}%`,
          height: "100%",
          background: color,
          borderRadius: 999,
          boxShadow: `0 0 8px ${color}`,
        }}
      />
    </div>
  );
}

// A compact stat/metric tile.
export function StatTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "accent" | "cyan" | "success" | "danger";
}) {
  const valueColor = tone
    ? { accent: "var(--accent)", cyan: "var(--cyan)", success: "var(--success)", danger: "var(--danger)" }[tone]
    : "var(--fg)";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
      <span className="eyebrow">{label}</span>
      <span style={{ fontFamily: "var(--font-display)", fontSize: "1.35rem", fontWeight: 600, color: valueColor }}>
        {value}
      </span>
      {hint && <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>{hint}</span>}
    </div>
  );
}

// Circular avatar with initials fallback.
export function Avatar({ name, src, size = 32 }: { name?: string | null; src?: string | null; size?: number }) {
  const initials = (name ?? "?")
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: src ? `center/cover url(${src})` : "linear-gradient(135deg, var(--violet), var(--cyan))",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: size * 0.36,
        fontWeight: 600,
        color: "#fff",
        flexShrink: 0,
      }}
    >
      {!src && initials}
    </div>
  );
}

// The "Active Orbit" visual: a central planet with stage nodes on an orbit ring.
// Static (animation-ready): nodes are positioned around the circle by index.
export type OrbitNode = { label: string; tone?: "accent" | "cyan" | "violet" | "muted" };

export function OrbitMap({ nodes, size = 260 }: { nodes: OrbitNode[]; size?: number }) {
  const cx = size / 2;
  const cy = size / 2;
  const orbitR = size * 0.38;
  const toneColor: Record<string, string> = {
    accent: "var(--accent)",
    cyan: "var(--cyan)",
    violet: "var(--violet)",
    muted: "var(--muted-2)",
  };
  return (
    <div style={{ position: "relative", width: size, height: size, margin: "0 auto" }}>
      <svg width={size} height={size} style={{ position: "absolute", inset: 0 }}>
        <circle cx={cx} cy={cy} r={orbitR} fill="none" stroke="var(--border-strong)" strokeDasharray="2 6" />
        <circle cx={cx} cy={cy} r={orbitR * 0.62} fill="none" stroke="var(--border)" strokeDasharray="2 8" />
        <defs>
          <radialGradient id="planet" cx="40%" cy="35%">
            <stop offset="0%" stopColor="#ffd08a" />
            <stop offset="55%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="#7a3c00" />
          </radialGradient>
        </defs>
        <circle cx={cx} cy={cy} r={size * 0.13} fill="url(#planet)" style={{ filter: "drop-shadow(0 0 20px rgba(245,165,36,0.55))" }} />
      </svg>
      {nodes.map((n, i) => {
        const angle = (i / nodes.length) * 2 * Math.PI - Math.PI / 2;
        const x = cx + orbitR * Math.cos(angle);
        const y = cy + orbitR * Math.sin(angle);
        const color = toneColor[n.tone ?? "muted"];
        return (
          <div
            key={n.label}
            style={{
              position: "absolute",
              left: x,
              top: y,
              transform: "translate(-50%, -50%)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "0.2rem",
            }}
          >
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: "50%",
                background: "var(--surface-solid)",
                border: `1.5px solid ${color}`,
                boxShadow: `0 0 10px ${color}`,
              }}
            />
            <span style={{ fontSize: "0.6rem", color: "var(--muted)", whiteSpace: "nowrap" }}>{n.label}</span>
          </div>
        );
      })}
    </div>
  );
}


