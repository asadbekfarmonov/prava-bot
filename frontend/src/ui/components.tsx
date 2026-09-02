import React, { useEffect, useRef, useState } from "react";
import type { MediaMeta } from "../types";

// --------------------------------------------------------------- Icons (inline, no dep)
type IconProps = { size?: number };
const svg = (path: React.ReactNode) => ({ size = 22 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{path}</svg>
);
export const IconHome = svg(<><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /></>);
export const IconPractice = svg(<><path d="M4 5h16" /><path d="M4 12h10" /><path d="M4 19h7" /><circle cx="18" cy="16" r="3" /></>);
export const IconTheory = svg(<><path d="M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2z" /><path d="M8 3v18" /></>);
export const IconExam = svg(<><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M9 8h6M9 12h6M9 16h4" /></>);
export const IconProfile = svg(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>);
export const IconChevron = svg(<path d="m9 6 6 6-6 6" />);
export const IconFlame = svg(<path d="M12 3c2 3 4 4.5 4 8a4 4 0 0 1-8 0c0-1.5.5-2.5 1-3 .3 1 1 1.5 1.5 1.5C10 8 11 5 12 3Z" />);
export const IconAlert = svg(<><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></>);
export const IconCheck = svg(<path d="m5 13 4 4L19 7" />);
export const IconInbox = svg(<><path d="M3 12h5l2 3h4l2-3h5" /><path d="M5 6h14l2 6v6H3v-6z" /></>);

// --------------------------------------------------------------- Screen / AppBar
export function Screen({ children, full }: { children: React.ReactNode; full?: boolean }) {
  return <div className={"ui-screen" + (full ? " ui-screen--full" : "")}>{children}</div>;
}

export function AppBar({ title, subtitle, right }: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <header className="ui-appbar">
      <div>
        <h1 className="ui-appbar__title">{title}</h1>
        {subtitle && <div className="ui-appbar__sub">{subtitle}</div>}
      </div>
      {right}
    </header>
  );
}

// --------------------------------------------------------------- Bottom nav
export type TabKey = "home" | "practice" | "theory" | "exam" | "profile";
export function BottomNav({ active, onChange, items }: {
  active: TabKey;
  onChange: (k: TabKey) => void;
  items: Array<{ key: TabKey; label: string; icon: (p: IconProps) => React.ReactElement }>;
}) {
  return (
    <nav className="ui-bottomnav" role="navigation" aria-label="Asosiy navigatsiya">
      {items.map((it) => {
        const Icon = it.icon;
        const isActive = active === it.key;
        return (
          <button key={it.key} className={"ui-navitem" + (isActive ? " ui-navitem--active" : "")}
            aria-current={isActive ? "page" : undefined} aria-label={it.label}
            onClick={() => onChange(it.key)}>
            <Icon size={22} />
            <span>{it.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

// --------------------------------------------------------------- Card / Button
export function Card({ children, accent, flat, className, ...rest }:
  React.HTMLAttributes<HTMLDivElement> & { accent?: boolean; flat?: boolean }) {
  const cls = ["ui-card", accent ? "ui-card--accent" : "", flat ? "ui-card--flat" : "", className || ""]
    .filter(Boolean).join(" ");
  return <div className={cls} {...rest}>{children}</div>;
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "onaccent";
export function Button({ variant = "primary", block, className, children, ...rest }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; block?: boolean }) {
  const cls = ["ui-btn", `ui-btn--${variant}`, block ? "ui-btn--block" : "", className || ""]
    .filter(Boolean).join(" ");
  return <button className={cls} {...rest}>{children}</button>;
}

// --------------------------------------------------------------- Stat / progress
export function StatBlock({ value, label }: { value: React.ReactNode; label: string }) {
  return (
    <div className="ui-stat">
      <span className="ui-stat__value">{value}</span>
      <span className="ui-stat__label">{label}</span>
    </div>
  );
}

export function ProgressBar({ value, max = 100, onAccent }: { value: number; max?: number; onAccent?: boolean }) {
  const pct = Math.max(0, Math.min(100, max ? (value / max) * 100 : 0));
  return (
    <div className={"ui-progressbar" + (onAccent ? " ui-progressbar--onaccent" : "")}
      role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <div className="ui-progressbar__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ProgressRing({ percent, size = 96, stroke = 9, label }:
  { percent: number | null; size?: number; stroke?: number; label?: string }) {
  const p = Math.max(0, Math.min(100, percent ?? 0));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (p / 100) * c;
  return (
    <svg className="ui-ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`}
      role="img" aria-label={label || `${Math.round(p)}%`}>
      <circle className="ui-ring__track" cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} fill="none" />
      <circle className="ui-ring__value" cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} fill="none"
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={percent === null ? c : offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text className="ui-ring__label" x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
        fontSize={size / 4.5}>{percent === null ? "—" : `${Math.round(p)}%`}</text>
    </svg>
  );
}

// --------------------------------------------------------------- QuestionMedia (the fix)
function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function QuestionMedia({ media, url, mediaType, alt }:
  { media?: MediaMeta | null; url?: string | null; mediaType?: string | null; alt?: string }) {
  const src = media?.url ?? url ?? null;
  const type = (media?.media_type ?? mediaType ?? "image").toLowerCase();
  const altText = alt ?? media?.alt ?? "";
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const reduced = prefersReducedMotion();

  useEffect(() => { setLoaded(false); setFailed(false); }, [src]);
  if (!src) return null;

  const ratio = media?.width && media?.height ? `${media.width} / ${media.height}` : undefined;
  const isVideo = type === "video";

  return (
    <div className="ui-media" style={ratio ? { aspectRatio: ratio } : undefined}>
      {!loaded && !failed && <Skeleton className="ui-media__skeleton" />}
      {failed ? (
        <div className="ui-media__fail" role="img" aria-label={altText || "media"}>
          <IconAlert size={28} />
          <span>Rasm yuklanmadi</span>
        </div>
      ) : isVideo ? (
        <>
          <video ref={videoRef} className="ui-media__el" src={src} poster={undefined}
            muted loop playsInline preload="metadata" autoPlay={!reduced}
            onLoadedData={() => setLoaded(true)} onError={() => setFailed(true)} aria-label={altText} />
          <button type="button" className="ui-media__replay"
            onClick={() => { const v = videoRef.current; if (v) { v.currentTime = 0; void v.play(); } }}>
            ↻ Qayta ko'rish
          </button>
        </>
      ) : (
        <img className="ui-media__el" src={src} alt={altText} loading="lazy"
          onLoad={() => setLoaded(true)} onError={() => setFailed(true)} />
      )}
    </div>
  );
}

// --------------------------------------------------------------- AnswerOption
export type OptionState = "idle" | "selected" | "correct" | "wrong";
export function AnswerOption({ label, text, state, disabled, onClick }:
  { label: string; text: string; state: OptionState; disabled?: boolean; onClick?: () => void }) {
  const cls = "ui-option" + (state !== "idle" ? ` ui-option--${state}` : "");
  return (
    <button className={cls} disabled={disabled} onClick={onClick}
      aria-pressed={state === "selected"}>
      <span className="ui-option__marker">{label}</span>
      <span>{text}</span>
    </button>
  );
}

// --------------------------------------------------------------- Expandable
export function Expandable({ title, defaultOpen, tone, children }:
  { title: string; defaultOpen?: boolean; tone?: "success" | "danger" | "accent"; children: React.ReactNode }) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div className={"ui-expandable" + (open ? " ui-expandable--open" : "")}>
      <button className="ui-expandable__head" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className={tone ? `ui-badge ui-badge--${tone}` : undefined} style={{ background: tone ? undefined : "transparent" }}>{title}</span>
        <span className="ui-expandable__chevron"><IconChevron size={18} /></span>
      </button>
      {open && <div className="ui-expandable__body">{children}</div>}
    </div>
  );
}

// --------------------------------------------------------------- Badge / Chip / Tabs
export function Badge({ children, tone }: { children: React.ReactNode; tone?: "success" | "warning" | "danger" | "accent" }) {
  return <span className={"ui-badge" + (tone ? ` ui-badge--${tone}` : "")}>{children}</span>;
}

export function Chip({ active, disabled, onClick, children }:
  { active?: boolean; disabled?: boolean; onClick?: () => void; children: React.ReactNode }) {
  return (
    <button className={"ui-chip" + (active ? " ui-chip--active" : "")} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

export function Tabs<T extends string>({ value, onChange, options }:
  { value: T; onChange: (v: T) => void; options: Array<[T, string]> }) {
  return (
    <div className="ui-tabs" role="tablist">
      {options.map(([key, label]) => (
        <button key={key} role="tab" aria-selected={value === key}
          className={"ui-tab" + (value === key ? " ui-tab--active" : "")} onClick={() => onChange(key)}>
          {label}
        </button>
      ))}
    </div>
  );
}

// --------------------------------------------------------------- ListRow
export function ListRow({ icon, title, subtitle, right, onClick }:
  { icon?: React.ReactNode; title: string; subtitle?: string; right?: React.ReactNode; onClick?: () => void }) {
  return (
    <button className="ui-listrow" onClick={onClick}>
      {icon && <span className="ui-listrow__icon">{icon}</span>}
      <span className="ui-listrow__body">
        <span className="ui-listrow__title">{title}</span>
        {subtitle && <span className="ui-listrow__sub">{subtitle}</span>}
      </span>
      {right ?? <span className="ui-listrow__chevron"><IconChevron size={18} /></span>}
    </button>
  );
}

// --------------------------------------------------------------- TopicMasteryBar
export function TopicMasteryBar({ label, mastery, hint }:
  { label: string; mastery: number; hint?: string }) {
  const pct = Math.round(mastery * 100);
  const color = mastery >= 0.75 ? "var(--success)" : mastery >= 0.5 ? "var(--warning)" : "var(--danger)";
  return (
    <div className="ui-mastery">
      <div className="ui-mastery__head">
        <span>{label}{hint && <span className="ui-muted"> · {hint}</span>}</span>
        <span className="ui-mastery__pct" style={{ color }}>{pct}%</span>
      </div>
      <div className="ui-mastery__bar"><div className="ui-mastery__fill" style={{ width: `${pct}%`, background: color }} /></div>
    </div>
  );
}

// --------------------------------------------------------------- Skeleton / Empty / Toast / Offline
export function Skeleton({ height, width, className, style }:
  { height?: number | string; width?: number | string; className?: string; style?: React.CSSProperties }) {
  return <div className={"ui-skeleton " + (className || "")}
    style={{ height: height ?? 16, width: width ?? "100%", ...style }} aria-hidden="true" />;
}

export function EmptyState({ icon, title, message, action }:
  { icon?: React.ReactNode; title?: string; message: string; action?: React.ReactNode }) {
  return (
    <div className="ui-empty">
      {icon && <span className="ui-empty__icon">{icon}</span>}
      {title && <span className="ui-empty__title">{title}</span>}
      <span>{message}</span>
      {action}
    </div>
  );
}

export function Toast({ message }: { message: string }) {
  return <div className="ui-toast" role="status">{message}</div>;
}

export function OfflineBar({ message }: { message: string }) {
  return <div className="ui-offline" role="status">{message}</div>;
}

// --------------------------------------------------------------- BottomSheet
export function BottomSheet({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="ui-sheet-backdrop" onClick={onClose}>
      <div className="ui-sheet" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
