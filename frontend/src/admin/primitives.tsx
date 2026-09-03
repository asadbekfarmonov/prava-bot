// Shared Admin mobile primitives (docs/spec/20 §5). Token-based, theme-aware, >=44px targets,
// visible focus, wrap long Uzbek labels. Reused across all Admin screens (no ad-hoc button styling).
import type { ReactNode } from "react";

// ------------------------------------------------------------------ mutation state
export type MutationState = "idle" | "saving" | "saved" | "error";

export const MUTATION_COPY: Record<Exclude<MutationState, "idle">, string> = {
  saving: "Saqlanmoqda...",
  saved: "Saqlandi",
  error: "Saqlanmadi"
};

// ------------------------------------------------------------------ status badge
const STATUS_LABELS: Record<string, string> = {
  draft: "Qoralama",
  needs_review: "Ko'rik kutilmoqda",
  reviewed: "Ko'rildi",
  published: "Nashr etilgan",
  needs_reverification: "Qayta tekshirish kerak",
  superseded: "Almashtirilgan",
  archived: "Arxivlangan"
};

export function AdminStatusBadge({ status }: { status: string }) {
  return <span className={`admin-badge admin-badge--${status}`}>{STATUS_LABELS[status] || status}</span>;
}

// ------------------------------------------------------------------ layout
export function AdminPageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="admin-pageheader">
      <div className="admin-pageheader__text">
        <h2 className="admin-pageheader__title">{title}</h2>
        {subtitle && <p className="admin-pageheader__sub">{subtitle}</p>}
      </div>
      {actions && <div className="admin-pageheader__actions">{actions}</div>}
    </div>
  );
}

export function AdminListCard({ title, subtitle, meta, badge, right, onClick }: {
  title: ReactNode; subtitle?: ReactNode; meta?: ReactNode; badge?: ReactNode; right?: ReactNode; onClick?: () => void;
}) {
  const Tag: "button" | "div" = onClick ? "button" : "div";
  return (
    <Tag className={"admin-listcard" + (onClick ? " admin-listcard--tap" : "")} onClick={onClick}>
      <div className="admin-listcard__main">
        <div className="admin-listcard__titlerow">
          <span className="admin-listcard__title">{title}</span>
          {badge}
        </div>
        {subtitle && <div className="admin-listcard__sub">{subtitle}</div>}
        {meta && <div className="admin-listcard__meta">{meta}</div>}
      </div>
      {right && <div className="admin-listcard__right">{right}</div>}
    </Tag>
  );
}

export function AdminStickyActions({ children }: { children: ReactNode }) {
  return <div className="admin-sticky-actions">{children}</div>;
}

// ------------------------------------------------------------------ search / filters
export function AdminSearchField({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <input className="admin-searchfield" type="search" inputMode="search" value={value}
      placeholder={placeholder || "Qidirish..."} onChange={(e) => onChange(e.target.value)} />
  );
}

export function AdminFilterChip({ label, active, onClick }: { label: string; active?: boolean; onClick: () => void }) {
  return (
    <button type="button" className={"admin-chip" + (active ? " is-active" : "")} onClick={onClick}>{label}</button>
  );
}

// ------------------------------------------------------------------ bottom sheet
export function AdminBottomSheet({ open, title, onClose, children }: { open: boolean; title?: string; onClose: () => void; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="admin-sheet-backdrop" onClick={onClose}>
      <div className="admin-sheet" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="admin-sheet__handle" />
        {title && <h2 className="admin-sheet__title">{title}</h2>}
        {children}
      </div>
    </div>
  );
}

export function AdminConfirmSheet({ open, title, message, confirmLabel = "Tasdiqlash", danger, onConfirm, onCancel }: {
  open: boolean; title: string; message?: string; confirmLabel?: string; danger?: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <AdminBottomSheet open={open} title={title} onClose={onCancel}>
      {message && <p className="muted">{message}</p>}
      <button type="button" className={"admin-btn " + (danger ? "admin-btn--danger" : "admin-btn--primary")} onClick={onConfirm}>{confirmLabel}</button>
      <button type="button" className="admin-sheet__cancel" onClick={onCancel}>Bekor qilish</button>
    </AdminBottomSheet>
  );
}

// ------------------------------------------------------------------ form fields
export function AdminField({ label, value, onChange, placeholder, type = "text", hint }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string; hint?: string;
}) {
  return (
    <label className="admin-formrow">
      <span className="admin-formrow__label">{label}</span>
      <input className="admin-input" type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      {hint && <span className="admin-formrow__hint">{hint}</span>}
    </label>
  );
}

export function AdminTextarea({ label, value, onChange, rows = 4, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; rows?: number; placeholder?: string;
}) {
  return (
    <label className="admin-formrow">
      <span className="admin-formrow__label">{label}</span>
      <textarea className="admin-input" rows={rows} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function AdminSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <label className="admin-formrow">
      <span className="admin-formrow__label">{label}</span>
      <select className="admin-input" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

// ------------------------------------------------------------------ status/feedback
export function AdminToast({ state, onRetry }: { state: MutationState; onRetry?: () => void }) {
  if (state === "idle") return null;
  return (
    <div className={"admin-toast admin-toast--" + state} role="status" aria-live="polite">
      <span>{MUTATION_COPY[state]}</span>
      {state === "error" && onRetry && (
        <button type="button" className="admin-toast__retry" onClick={onRetry}>Qayta urinish</button>
      )}
    </div>
  );
}

export function AdminLoadingState({ label = "Yuklanmoqda..." }: { label?: string }) {
  return <div className="admin-state admin-state--loading">{label}</div>;
}

export function AdminErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="admin-state admin-state--error">
      <p>{message}</p>
      {onRetry && <button type="button" className="admin-btn admin-btn--secondary" onClick={onRetry}>Qayta urinish</button>}
    </div>
  );
}

export function AdminEmptyState({ message }: { message: string }) {
  return <div className="admin-state admin-state--empty">{message}</div>;
}
