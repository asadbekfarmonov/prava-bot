import { ADMIN_TABS } from "./routes";
import type { AdminTab } from "./routes";

// Top bar (docs/spec/20 §3): min-height 52px + safe-top. On wide screens the
// quick-create action lives here (mobile uses the floating button instead).
export function AdminTopBar({ tab, onQuickCreate }: { tab: AdminTab; onQuickCreate: () => void }) {
  const label = ADMIN_TABS.find((t) => t.tab === tab)?.label ?? "Admin";
  return (
    <header className="admin-topbar">
      <h1 className="admin-topbar__title">{label}</h1>
      <button type="button" className="admin-topbar__create" onClick={onQuickCreate} aria-label="Yangi yaratish">
        + Yangi
      </button>
    </header>
  );
}
