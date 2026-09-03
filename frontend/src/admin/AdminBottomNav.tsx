import { ADMIN_TABS } from "./routes";
import type { AdminTab } from "./routes";

// Five-item Admin bottom navigation (docs/spec/20 §1, §3). Mobile only (hidden >=768px
// where the sidebar takes over). Item min-height 64px + safe-bottom via CSS.
export function AdminBottomNav({ active, onSelect }: { active: AdminTab; onSelect: (tab: AdminTab) => void }) {
  return (
    <nav className="admin-bottomnav" aria-label="Admin navigatsiyasi">
      {ADMIN_TABS.map((t) => (
        <button
          key={t.tab}
          type="button"
          className={"admin-bottomnav__item" + (active === t.tab ? " is-active" : "")}
          aria-current={active === t.tab ? "page" : undefined}
          onClick={() => onSelect(t.tab)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
