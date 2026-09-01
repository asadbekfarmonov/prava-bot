import type {
  AnswerResult,
  DashboardOut,
  MistakeItem,
  MockAttemptState,
  MockReview,
  NextQuestion,
  ProfileOut,
  RankingOut,
  ReadinessOut,
  UserOut
} from "./types";

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
  createSession: (topic: string | null, source?: string) =>
    request<{ id: string }>("/api/practice/sessions", {
      method: "POST",
      body: JSON.stringify({ topic, source })
    }),
  nextQuestion: (topic: string | null, source?: string) => {
    const params = new URLSearchParams();
    if (topic) params.set("topic", topic);
    if (source) params.set("source", source);
    const qs = params.toString();
    return request<NextQuestion>(`/api/practice/questions/next${qs ? `?${qs}` : ""}`);
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
  ,
  startMock: () =>
    request<MockAttemptState>("/api/mock/attempts", { method: "POST", body: JSON.stringify({}) }),
  currentMock: () => request<MockAttemptState>("/api/mock/attempts/current"),
  getMock: (id: string) => request<MockAttemptState>(`/api/mock/attempts/${id}`),
  saveMockAnswer: (
    id: string,
    questionVersionId: string,
    selectedOptionId: string | null,
    markedForReview: boolean
  ) =>
    request<{ saved: boolean; remaining_seconds: number }>(
      `/api/mock/attempts/${id}/answers`,
      {
        method: "POST",
        body: JSON.stringify({
          question_version_id: questionVersionId,
          selected_option_id: selectedOptionId,
          marked_for_review: markedForReview
        })
      }
    ),
  submitMock: (id: string) =>
    request<MockAttemptState>(`/api/mock/attempts/${id}/submit`, { method: "POST", body: JSON.stringify({}) }),
  reviewMock: (id: string) => request<MockReview>(`/api/mock/attempts/${id}/review`),
  readiness: () => request<ReadinessOut>("/api/readiness"),
  dashboard: () => request<DashboardOut>("/api/dashboard"),
  ranking: (range: "week" | "month" | "all") =>
    request<RankingOut>(`/api/ranking?range=${range}`),
  mistakes: () => request<{ mistakes: MistakeItem[] }>("/api/practice/mistakes")
};

export const adminApi = {
  overview: () => request<import("./types").AdminOverview>("/api/admin/overview"),
  listQuestions: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request<{ total: number; items: import("./types").AdminQuestionListItem[] }>(
      `/api/admin/questions${qs ? `?${qs}` : ""}`
    );
  },
  createQuestion: (payload: import("./types").AdminQuestionInput) =>
    request<import("./types").AdminVersionOut>("/api/admin/questions", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  editQuestion: (id: string, payload: import("./types").AdminQuestionInput) =>
    request<import("./types").AdminVersionOut>(`/api/admin/questions/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  submitReview: (vid: string) =>
    request<import("./types").AdminVersionOut>(`/api/admin/versions/${vid}/submit-review`, { method: "POST", body: "{}" }),
  review: (vid: string) =>
    request<import("./types").AdminVersionOut>(`/api/admin/versions/${vid}/review`, { method: "POST", body: "{}" }),
  publish: (vid: string) =>
    request<import("./types").AdminVersionOut>(`/api/admin/versions/${vid}/publish`, { method: "POST", body: "{}" }),
  qa: (qid: string) => request<import("./types").QaPayload>(`/api/admin/questions/${qid}/qa`),
  searchRules: (q: string) =>
    request<{ rules: import("./types").AdminRuleOut[] }>(`/api/admin/rules${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  reports: (status?: string) =>
    request<{ reports: import("./types").AdminReport[] }>(`/api/admin/reports${status ? `?status=${status}` : ""}`),
  resolveReport: (id: string, action: "resolve" | "reject" | "triage") =>
    request<{ id: string; status: string }>(`/api/admin/reports/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ action })
    }),
  uploadMedia: async (file: File): Promise<import("./types").MediaOut> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/admin/media", { method: "POST", credentials: "include", body: form });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail || detail;
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return (await res.json()) as import("./types").MediaOut;
  }
};
