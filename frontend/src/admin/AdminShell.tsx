import { useState } from "react";
import { ADMIN_TABS } from "./routes";
import type { AdminNav } from "./useAdminNavigation";
import { AdminTopBar } from "./AdminTopBar";
import { AdminBottomNav } from "./AdminBottomNav";
import { QuickCreateSheet } from "./QuickCreateSheet";
import type { QuickCreateKind } from "./QuickCreateSheet";
import { Dashboard, QuestionsSection, TheorySection, ReviewQueue, ReportsQueue } from "./legacy";

function Placeholder({ title }: { title: string }) {
  return (
    <div className="admin-page">
      <h2>{title}</h2>
      <p className="muted">Bu bo'lim keyingi bosqichda to'liq ishga tushiriladi.</p>
    </div>
  );
}

function MoreHub({ canReview, isAdmin, nav }: { canReview: boolean; isAdmin: boolean; nav: AdminNav }) {
  const items: { label: string; go: () => void; show: boolean }[] = [
    { label: "Ko'rik navbati", go: () => nav.push({ kind: "review" }), show: canReview },
    { label: "Shikoyatlar", go: () => nav.push({ kind: "reports" }), show: canReview },
    { label: "Qoidalar", go: () => nav.push({ kind: "rules" }), show: isAdmin },
    { label: "Media kutubxona", go: () => nav.push({ kind: "media" }), show: true },
    { label: "Global qidiruv", go: () => nav.push({ kind: "admin-search" }), show: true },
    { label: "Adminlar", go: () => nav.push({ kind: "admins" }), show: isAdmin },
    { label: "Audit jurnali", go: () => nav.push({ kind: "audit" }), show: isAdmin },
    { label: "Import / eksport", go: () => nav.push({ kind: "imports" }), show: isAdmin }
  ];
  return (
    <div className="admin-page">
      <h2>Ko'proq</h2>
      <div className="admin-morelist">
        {items.filter((i) => i.show).map((i) => (
          <button key={i.label} type="button" className="admin-morelist__item" onClick={i.go}>{i.label}</button>
        ))}
      </div>
    </div>
  );
}

export function AdminShell({ role, nav }: { role: string | null; nav: AdminNav }) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const canReview = role === "content_reviewer" || role === "admin" || role === "superadmin";
  const isAdmin = role === "admin" || role === "superadmin";
  const { current, activeTab } = nav;

  function quickPick(kind: QuickCreateKind) {
    setSheetOpen(false);
    if (kind === "question") nav.selectTab("questions");
    else if (kind === "assessment") nav.selectTab("assessments");
    else if (kind === "rule") nav.push({ kind: "rules" });
    else nav.selectTab("theory"); // article/sign/marking/gesture/light -> Nazariya (deep routes land in later phases)
  }

  function renderContent() {
    // Routes owned by "Ko'proq" and other explicit detail routes (Phase-1 compatibility).
    switch (current.kind) {
      case "review":
        return canReview ? <ReviewQueue canReview={canReview} /> : <ReportsQueue />;
      case "reports":
        return <ReportsQueue />;
      case "rules":
        return <Placeholder title="Qoidalar" />;
      case "media":
        return <Placeholder title="Media kutubxona" />;
      case "admin-search":
        return <Placeholder title="Global qidiruv" />;
      case "admins":
        return <Placeholder title="Adminlar" />;
      case "audit":
        return <Placeholder title="Audit jurnali" />;
      case "imports":
        return <Placeholder title="Import / eksport" />;
      default:
        break;
    }
    switch (activeTab) {
      case "dashboard":
        return <Dashboard onGoReports={() => nav.push({ kind: "reports" })} onGoReview={() => nav.push({ kind: canReview ? "review" : "reports" })} />;
      case "questions":
        return <QuestionsSection canReview={canReview} />;
      case "assessments":
        return <Placeholder title="Testlar" />;
      case "theory":
        return <TheorySection canReview={canReview} />;
      case "more":
        return <MoreHub canReview={canReview} isAdmin={isAdmin} nav={nav} />;
      default:
        return null;
    }
  }

  return (
    <div className="admin-shell">
      <AdminTopBar tab={activeTab} onQuickCreate={() => setSheetOpen(true)} />
      <div className="admin-body">
        <aside className="admin-sidebar" aria-label="Admin yon menyu">
          {ADMIN_TABS.map((t) => (
            <button
              key={t.tab}
              type="button"
              className={"admin-sidebar__item" + (activeTab === t.tab ? " is-active" : "")}
              onClick={() => nav.selectTab(t.tab)}
            >
              {t.label}
            </button>
          ))}
        </aside>
        <main className="admin-content">{renderContent()}</main>
      </div>
      <button type="button" className="admin-fab" aria-label="Yangi yaratish" onClick={() => setSheetOpen(true)}>+</button>
      <AdminBottomNav active={activeTab} onSelect={nav.selectTab} />
      <QuickCreateSheet open={sheetOpen} isAdmin={isAdmin} onPick={quickPick} onClose={() => setSheetOpen(false)} />
    </div>
  );
}
