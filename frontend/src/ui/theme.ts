// Apply Telegram themeParams + colorScheme to the CSS custom-property tokens, with a
// system fallback. Also mirrors safe-area insets into --safe-top / --safe-bottom.
import {
  getColorScheme,
  getSafeAreaInsets,
  getThemeParams,
  onTelegramEvent
} from "../telegram";

function setVar(name: string, value?: string) {
  if (value) document.documentElement.style.setProperty(name, value);
}

export function applyTheme(): void {
  const root = document.documentElement;
  const scheme = getColorScheme();
  const prefersDark =
    window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const dark = scheme ? scheme === "dark" : prefersDark;
  root.setAttribute("data-theme", dark ? "dark" : "light");

  // Map Telegram themeParams onto our tokens where provided.
  const tp = getThemeParams();
  setVar("--bg", tp.secondary_bg_color || tp.bg_color);
  setVar("--surface", tp.bg_color);
  setVar("--surface-2", tp.secondary_bg_color);
  setVar("--text", tp.text_color);
  setVar("--text-muted", tp.hint_color);
  setVar("--accent", tp.button_color);
  setVar("--accent-contrast", tp.button_text_color);
  setVar("--danger", tp.destructive_text_color);

  const inset = getSafeAreaInsets();
  root.style.setProperty("--safe-top", `${inset.top}px`);
  root.style.setProperty("--safe-bottom", `${inset.bottom}px`);
}

// Re-apply on Telegram theme/viewport changes and on system scheme change.
export function watchTheme(): void {
  applyTheme();
  onTelegramEvent("themeChanged", applyTheme);
  onTelegramEvent("viewportChanged", applyTheme);
  onTelegramEvent("safeAreaChanged", applyTheme);
  onTelegramEvent("contentSafeAreaChanged", applyTheme);
  if (window.matchMedia) {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener?.("change", applyTheme);
  }
}
