declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string;
        ready?: () => void;
        expand?: () => void;
      };
    };
  }
}

export function getTelegramInitData(): string {
  return window.Telegram?.WebApp?.initData || "";
}

export function readyTelegram(): void {
  try {
    window.Telegram?.WebApp?.ready?.();
    window.Telegram?.WebApp?.expand?.();
  } catch {
    /* not running inside Telegram */
  }
}
