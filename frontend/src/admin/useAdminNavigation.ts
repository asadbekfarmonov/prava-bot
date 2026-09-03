import { useCallback, useEffect, useRef, useState } from "react";
import { hideBackButton, showBackButton } from "../telegram";
import type { AdminRoute, AdminTab } from "./routes";
import { tabForRoute } from "./routes";

// Route-stack navigation for the Admin studio (docs/spec/20 §1). No React Router.
// - bottom-nav tap resets the stack to a single {kind:"tab"} route;
// - opening a detail pushes one route;
// - Telegram BackButton pops one route; at the root it calls onExit() (-> Profile);
// - an editor unsaved-change guard (if registered) runs before any pop/exit.
export function useAdminNavigation(onExit: () => void) {
  const [stack, setStack] = useState<AdminRoute[]>([{ kind: "tab", tab: "dashboard" }]);
  // Guard returns true to allow leaving, false to cancel (e.g. unsaved changes).
  const guardRef = useRef<null | (() => boolean)>(null);
  const setLeaveGuard = useCallback((fn: null | (() => boolean)) => { guardRef.current = fn; }, []);
  const canLeave = useCallback(() => (guardRef.current ? guardRef.current() : true), []);

  const current = stack[stack.length - 1];
  const activeTab: AdminTab = tabForRoute(current);

  const push = useCallback((r: AdminRoute) => {
    if (!canLeave()) return;
    guardRef.current = null;
    setStack((s) => [...s, r]);
  }, [canLeave]);

  const replace = useCallback((r: AdminRoute) => {
    guardRef.current = null;
    setStack((s) => [...s.slice(0, -1), r]);
  }, []);

  const selectTab = useCallback((tab: AdminTab) => {
    if (!canLeave()) return;
    guardRef.current = null;
    setStack([{ kind: "tab", tab }]);
  }, [canLeave]);

  const back = useCallback(() => {
    if (!canLeave()) return;
    guardRef.current = null;
    setStack((s) => {
      if (s.length > 1) return s.slice(0, -1);
      onExit();
      return s;
    });
  }, [canLeave, onExit]);

  // Telegram BackButton is visible for the whole Admin session.
  useEffect(() => {
    const cleanup = showBackButton(back);
    return () => {
      cleanup?.();
      hideBackButton();
    };
  }, [back]);

  return { stack, current, activeTab, push, replace, selectTab, back, setLeaveGuard };
}

export type AdminNav = ReturnType<typeof useAdminNavigation>;
