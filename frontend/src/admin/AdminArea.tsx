import { useEffect } from "react";
import "./admin.css";
import { AdminShell } from "./AdminShell";
import { useAdminNavigation } from "./useAdminNavigation";

// Admin studio root (docs/spec/20). Mounts the mobile-first shell + route-stack nav.
// While Admin is open we tag <body> so the consumer `.ui-app { max-width:640px }`
// does not constrain the wide (>=768px) Admin workspace.
export function AdminArea({ role, onExit }: { role: string | null; onExit: () => void }) {
  const nav = useAdminNavigation(onExit);
  useEffect(() => {
    document.body.classList.add("admin-open");
    return () => document.body.classList.remove("admin-open");
  }, []);
  return (
    <div className="admin-root">
      <AdminShell role={role} nav={nav} />
    </div>
  );
}
