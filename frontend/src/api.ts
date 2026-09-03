import type {
  AnswerResult,
  DashboardOut,
  FullProfileOut,
  HomeSummary,
  MistakeItem,
  MockAttemptState,
  MockReview,
  NextAction,
  NextQuestion,
  RankingOut,
  ReadinessOut,
  TopicProgressRow,
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
  me: () => request<{ user: UserOut; profile: FullProfileOut | null }>("/api/auth/me"),
  saveProfile: (patch: Partial<{
    display_name: string;
    target_exam_date: string | null;
    daily_goal: number | null;
    ranking_name: string | null;
    show_on_ranking: boolean;
    timezone: string;
  }> & { display_name: string }) =>
    request<{ profile: FullProfileOut }>("/api/profile", {
      method: "PUT",
      body: JSON.stringify({ category: "B", language: "uz", ...patch })
    }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST", body: "{}" }),
  home: () => request<HomeSummary>("/api/home"),
  nextAction: () => request<NextAction>("/api/practice/next-action"),
  topicProgress: () => request<{ topics: TopicProgressRow[] }>("/api/progress/topics"),
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

export const theoryApi = {
  sections: () => request<{ sections: import("./types").TheorySectionCard[] }>("/api/theory/sections"),
  section: (slug: string) => request<import("./types").TheorySection>(`/api/theory/sections/${encodeURIComponent(slug)}`),
  article: (slug: string) => request<import("./types").TheoryArticle>(`/api/theory/articles/${encodeURIComponent(slug)}`),
  search: (q: string) =>
    request<{ results: import("./types").SearchResult[] }>(`/api/theory/search?q=${encodeURIComponent(q)}`),
  signs: (family?: string) =>
    request<{ signs: import("./types").SignCard[] }>(`/api/theory/signs${family ? `?family=${family}` : ""}`),
  sign: (code: string) => request<import("./types").SignDetail>(`/api/theory/signs/${encodeURIComponent(code)}`),
  markings: () => request<{ markings: import("./types").MarkingCard[] }>("/api/theory/markings"),
  marking: (id: string) => request<import("./types").MarkingDetail>(`/api/theory/markings/${id}`),
  gestures: () => request<{ gestures: import("./types").GestureCard[] }>("/api/theory/gestures"),
  gesture: (id: string) => request<import("./types").GestureDetail>(`/api/theory/gestures/${id}`),
  lights: () => request<{ lights: import("./types").LightCard[] }>("/api/theory/lights"),
  light: (id: string) => request<import("./types").LightDetail>(`/api/theory/lights/${id}`),
  byRule: (code: string) => request<{ rule: import("./types").TheoryRule; articles: import("./types").TheoryArticleCard[]; signs: import("./types").SignCard[] }>(`/api/theory/by-rule/${encodeURIComponent(code)}`),
  markProgress: (targetType: string, targetId: string) =>
    request<{ state: string }>("/api/theory/progress", {
      method: "POST",
      body: JSON.stringify({ target_type: targetType, target_id: targetId })
    }),
  favorites: () => request<{ favorites: import("./types").FavoriteItem[] }>("/api/theory/favorites"),
  addFavorite: (targetType: string, targetId: string) =>
    request<{ id: string }>("/api/theory/favorites", {
      method: "POST",
      body: JSON.stringify({ target_type: targetType, target_id: targetId })
    }),
  removeFavorite: (id: string) =>
    fetch(`/api/theory/favorites/${id}`, { method: "DELETE", credentials: "include" }).then((r) => {
      if (!r.ok && r.status !== 204) throw new Error("delete failed");
    }),
  startPractice: (targetType: "article" | "sign", targetId: string) =>
    request<import("./types").TheoryPracticeStart>("/api/theory/practice/start", {
      method: "POST",
      body: JSON.stringify({ target_type: targetType, target_id: targetId })
    })
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
  },

  // ---- Theory studio (docs/spec/19). All server-side role-gated. ----
  theoryListSections: (includeUnpublished = true) =>
    request<{ sections: import("./types").AdminSectionListItem[] }>(
      `/api/admin/theory/sections?include_unpublished=${String(includeUnpublished)}`
    ),
  theoryListArticles: (sectionId?: string, includeUnpublished = true) => {
    const p = new URLSearchParams();
    if (sectionId) p.set("section_id", sectionId);
    p.set("include_unpublished", String(includeUnpublished));
    return request<{ articles: import("./types").AdminArticleListItem[] }>(
      `/api/admin/theory/articles?${p.toString()}`
    );
  },
  theoryListSigns: (family?: string, includeUnpublished = true) => {
    const p = new URLSearchParams();
    if (family) p.set("family", family);
    p.set("include_unpublished", String(includeUnpublished));
    return request<{ signs: import("./types").AdminSignListItem[] }>(
      `/api/admin/theory/signs?${p.toString()}`
    );
  },
  theoryListMarkings: (includeUnpublished = true) =>
    request<{ markings: import("./types").AdminMarkingListItem[] }>(
      `/api/admin/theory/markings?include_unpublished=${String(includeUnpublished)}`
    ),
  theoryListGestures: (includeUnpublished = true) =>
    request<{ gestures: import("./types").AdminGestureListItem[] }>(
      `/api/admin/theory/gestures?include_unpublished=${String(includeUnpublished)}`
    ),
  theoryListLights: (includeUnpublished = true) =>
    request<{ lights: import("./types").AdminLightListItem[] }>(
      `/api/admin/theory/lights?include_unpublished=${String(includeUnpublished)}`
    ),

  // Signs
  theoryCreateSign: (payload: import("./types").SignCreateInput) =>
    request<import("./types").SignCreateOut>("/api/admin/theory/signs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  theoryEditSign: (id: string, payload: import("./types").SignContentInput) =>
    request<import("./types").SignCreateOut>(`/api/admin/theory/signs/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  theorySubmitSign: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/sign-versions/${vid}/submit-review`, { method: "POST", body: "{}" }),
  theoryReviewSign: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/sign-versions/${vid}/review`, { method: "POST", body: "{}" }),
  theoryPublishSign: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/sign-versions/${vid}/publish`, { method: "POST", body: "{}" }),

  // Markings
  theoryCreateMarking: (payload: import("./types").MarkingCreateInput) =>
    request<import("./types").MarkingCreateOut>("/api/admin/theory/markings", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  theoryEditMarking: (id: string, payload: import("./types").MarkingContentInput) =>
    request<import("./types").MarkingCreateOut>(`/api/admin/theory/markings/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  theorySubmitMarking: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/marking-versions/${vid}/submit-review`, { method: "POST", body: "{}" }),
  theoryReviewMarking: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/marking-versions/${vid}/review`, { method: "POST", body: "{}" }),
  theoryPublishMarking: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/marking-versions/${vid}/publish`, { method: "POST", body: "{}" }),

  // Gestures
  theoryCreateGesture: (payload: import("./types").GestureCreateInput) =>
    request<import("./types").GestureCreateOut>("/api/admin/theory/gestures", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  theoryEditGesture: (id: string, payload: import("./types").GestureContentInput) =>
    request<import("./types").GestureCreateOut>(`/api/admin/theory/gestures/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  theorySubmitGesture: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/gesture-versions/${vid}/submit-review`, { method: "POST", body: "{}" }),
  theoryReviewGesture: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/gesture-versions/${vid}/review`, { method: "POST", body: "{}" }),
  theoryPublishGesture: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/gesture-versions/${vid}/publish`, { method: "POST", body: "{}" }),

  // Lights
  theoryCreateLight: (payload: import("./types").LightCreateInput) =>
    request<import("./types").LightCreateOut>("/api/admin/theory/lights", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  theoryEditLight: (id: string, payload: import("./types").LightContentInput) =>
    request<import("./types").LightCreateOut>(`/api/admin/theory/lights/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  theorySubmitLight: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/light-versions/${vid}/submit-review`, { method: "POST", body: "{}" }),
  theoryReviewLight: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/light-versions/${vid}/review`, { method: "POST", body: "{}" }),
  theoryPublishLight: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/light-versions/${vid}/publish`, { method: "POST", body: "{}" }),

  // ---- Sections (create/translate/publish) ----
  theoryCreateSection: (payload: import("./types").AdminSectionCreateInput) =>
    request<import("./types").SectionCreateOut>("/api/admin/theory/sections", { method: "POST", body: JSON.stringify(payload) }),
  theoryTranslateSection: (id: string, payload: { language?: string; title: string; subtitle?: string }) =>
    request<{ id: string; status: string }>(`/api/admin/theory/sections/${id}/translation`, { method: "PUT", body: JSON.stringify(payload) }),
  theoryPublishSection: (id: string) =>
    request<{ id: string; status: string }>(`/api/admin/theory/sections/${id}/publish`, { method: "POST", body: "{}" }),

  // ---- Articles (create + block editor content + review lifecycle) ----
  theoryCreateArticle: (payload: import("./types").AdminArticleCreateInput) =>
    request<import("./types").ArticleVersionOut>("/api/admin/theory/articles", { method: "POST", body: JSON.stringify(payload) }),
  theoryEditArticle: (articleId: string, payload: import("./types").AdminArticleContentInput) =>
    request<import("./types").ArticleVersionOut>(`/api/admin/theory/articles/${articleId}`, { method: "PUT", body: JSON.stringify(payload) }),
  theorySubmitArticle: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/article-versions/${vid}/submit-review`, { method: "POST", body: "{}" }),
  theoryReviewArticle: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/article-versions/${vid}/review`, { method: "POST", body: "{}" }),
  theoryPublishArticle: (vid: string) =>
    request<import("./types").TheoryVersionOut>(`/api/admin/theory/article-versions/${vid}/publish`, { method: "POST", body: "{}" }),

  theoryReviewQueue: () =>
    request<import("./types").ReviewQueueOut>("/api/admin/theory/review-queue")
};
