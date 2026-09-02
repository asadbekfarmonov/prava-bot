// Telegram Mini App SDK wrapper (docs/spec/16 Phase 21).
// Exposes only what the app needs: init data, ready/expand, themeParams + colorScheme,
// BackButton show/hide, safe-area insets, stable viewport height, and vertical-swipe
// control (disabled during an active mock so a swipe can't close the exam).

type ThemeParams = Record<string, string>;

interface TelegramWebApp {
  initData?: string;
  version?: string;
  colorScheme?: "light" | "dark";
  themeParams?: ThemeParams;
  viewportStableHeight?: number;
  viewportHeight?: number;
  isExpanded?: boolean;
  ready?: () => void;
  expand?: () => void;
  enableClosingConfirmation?: () => void;
  disableClosingConfirmation?: () => void;
  disableVerticalSwipes?: () => void;
  enableVerticalSwipes?: () => void;
  onEvent?: (event: string, cb: () => void) => void;
  offEvent?: (event: string, cb: () => void) => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  BackButton?: {
    show?: () => void;
    hide?: () => void;
    onClick?: (cb: () => void) => void;
    offClick?: (cb: () => void) => void;
  };
  MainButton?: {
    setText?: (text: string) => void;
    show?: () => void;
    hide?: () => void;
    onClick?: (cb: () => void) => void;
    offClick?: (cb: () => void) => void;
  };
  SafeAreaInset?: { top: number; bottom: number; left: number; right: number };
  contentSafeAreaInset?: { top: number; bottom: number; left: number; right: number };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function tg(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp;
}

export function getTelegramInitData(): string {
  return tg()?.initData || "";
}

export function readyTelegram(): void {
  try {
    const w = tg();
    w?.ready?.();
    w?.expand?.();
  } catch {
    /* not running inside Telegram */
  }
}

export function getColorScheme(): "light" | "dark" {
  return tg()?.colorScheme || "light";
}

export function getThemeParams(): ThemeParams {
  return tg()?.themeParams || {};
}

export function getViewportHeight(): number {
  const w = tg();
  return w?.viewportStableHeight || w?.viewportHeight || window.innerHeight;
}

export function getSafeAreaInsets(): { top: number; bottom: number } {
  const w = tg();
  const sa = w?.SafeAreaInset;
  const content = w?.contentSafeAreaInset;
  return {
    top: (sa?.top ?? 0) + (content?.top ?? 0),
    bottom: (sa?.bottom ?? 0) + (content?.bottom ?? 0)
  };
}

// Subscribe to theme/viewport changes; returns an unsubscribe fn.
export function onTelegramEvent(event: string, cb: () => void): () => void {
  const w = tg();
  w?.onEvent?.(event, cb);
  return () => w?.offEvent?.(event, cb);
}

// BackButton wiring for in-app detail navigation.
export function showBackButton(onClick: () => void): () => void {
  const w = tg();
  const bb = w?.BackButton;
  if (!bb) return () => undefined;
  bb.onClick?.(onClick);
  bb.show?.();
  return () => {
    bb.offClick?.(onClick);
    bb.hide?.();
  };
}

export function hideBackButton(): void {
  tg()?.BackButton?.hide?.();
}

// Lock the mini-app during an active mock: disable vertical swipe-to-close +
// closing confirmation so a stray gesture can't abandon the exam.
export function lockForMock(): void {
  const w = tg();
  try {
    w?.disableVerticalSwipes?.();
    w?.enableClosingConfirmation?.();
  } catch {
    /* older client */
  }
}

export function unlockFromMock(): void {
  const w = tg();
  try {
    w?.enableVerticalSwipes?.();
    w?.disableClosingConfirmation?.();
  } catch {
    /* older client */
  }
}
