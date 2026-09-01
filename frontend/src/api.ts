import type { AnswerResult, NextQuestion, ProfileOut, UserOut } from "./types";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  devConfig: () => request<{ dev_auth_enabled: boolean; app_env: string }>("/api/dev/config"),
  telegramLogin: (initData: string) =>
    request<{ user: UserOut }>("/api/auth/telegram-mini-app", {
      method: "POST",
      body: JSON.stringify({ init_data: initData })
    }),
  devLogin: () =>
    request<{ user: UserOut }>("/api/dev/login", {
      method: "POST",
      body: JSON.stringify({ telegram_id: 1001, first_name: "Dev" })
    }),
  me: () => request<{ user: UserOut; profile: ProfileOut | null }>("/api/auth/me"),
  saveProfile: (displayName: string) =>
    request<{ profile: ProfileOut }>("/api/profile", {
      method: "PUT",
      body: JSON.stringify({ display_name: displayName, category: "B", language: "uz" })
    }),
  createSession: (topic: string | null) =>
    request<{ id: string }>("/api/practice/sessions", {
      method: "POST",
      body: JSON.stringify({ topic })
    }),
  nextQuestion: (topic: string | null) => {
    const qs = topic ? `?topic=${encodeURIComponent(topic)}` : "";
    return request<NextQuestion>(`/api/practice/questions/next${qs}`);
  },
  submitAnswer: (sessionId: string, questionId: string, optionId: string) =>
    request<AnswerResult>("/api/practice/answers", {
      method: "POST",
      body: JSON.stringify({
        practice_session_id: sessionId,
        question_id: questionId,
        selected_option_id: optionId
      })
    })
};
