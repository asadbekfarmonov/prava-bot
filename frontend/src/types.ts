export interface UserOut {
  id: string;
  telegram_id: string;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  photo_url: string | null;
  is_admin: boolean;
  admin_role: string | null;
  onboarding_completed: boolean;
}

export interface ProfileOut {
  display_name: string | null;
  category: string;
  language: string;
  onboarding_completed: boolean;
}

export interface MediaMeta {
  media_id: string;
  content_hash: string;
  media_type: string; // "image" | "gif" | "video"
  url: string;
  alt: string | null;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
}

export interface NextOption {
  id: string;
  position: number;
  text: string;
}

export interface NextQuestion {
  question_id: string;
  question_version_id: string;
  topic: string | null;
  is_sign_question: boolean;
  prompt: string;
  media_id: string | null;
  media: MediaMeta | null;
  options: NextOption[];
}

export interface GradedOption {
  id: string;
  position: number;
  text: string;
  is_correct: boolean;
  explanation: string;
}

export interface RuleOut {
  code: string;
  title: string | null;
  text: string;
  source_url: string;
  rule_version: number;
}

export interface AnswerResult {
  is_correct: boolean;
  selected_option_id: string | null;
  correct_option_id: string | null;
  short_explanation: string;
  options: GradedOption[];
  rule: RuleOut | null;
}

// ---- Mock exam (exam mode) ----
export interface MockQuestionView {
  position: number;
  question_version_id: string;
  prompt: string;
  media_id: string | null;
  media: MediaMeta | null;
  options: NextOption[];
  selected_option_id: string | null;
  marked_for_review: boolean;
}

export interface MockResult {
  correct_count: number;
  answered_count: number;
  question_count: number;
  pass_correct: number;
  passed: boolean;
  per_topic: Record<string, { total: number; correct: number }>;
  missed: Array<{
    position: number;
    question_version_id: string;
    topic: string;
    correct_option_id: string | null;
  }>;
  avg_answer_time_seconds: number | null;
}

export interface MockAttemptState {
  id: string;
  status: "in_progress" | "completed" | "abandoned";
  category: string;
  language: string;
  started_at: string;
  expires_at: string;
  completed_at: string | null;
  question_count: number;
  time_limit_seconds: number;
  pass_correct: number;
  exam_config_version: number;
  remaining_seconds: number;
  correct_count: number | null;
  answered_count: number | null;
  passed: boolean | null;
  result: MockResult | null;
  questions: MockQuestionView[];
}

export interface MockReviewItem {
  position: number;
  question_version_id: string;
  prompt: string;
  media_id: string | null;
  media: MediaMeta | null;
  short_explanation: string;
  selected_option_id: string | null;
  is_correct: boolean;
  correct_option_id: string | null;
  options: GradedOption[];
  rule: RuleOut | null;
}

export interface MockReview extends MockAttemptState {
  items: MockReviewItem[];
}

// ---- Admin studio ----
export interface AdminOverview {
  counts: Record<string, number>;
  topic_coverage: Record<string, number>;
  questions_without_media_where_likely_needed: string[];
  open_reports: number;
  media_storage: { object_count: number; total_bytes: number };
}

export interface AdminQuestionListItem {
  id: string;
  topic: string;
  category: string;
  is_sign_question: boolean;
  lifecycle_status: string;
  current_version_id: string | null;
  working_version_id: string | null;
  prompt: string;
  has_media: boolean;
}

export interface AdminRuleOut {
  id: string;
  code: string;
  title: string | null;
  text: string;
  version: number;
  source_url: string;
  status: string;
}

export interface AdminOptionInput {
  text: string;
  explanation: string;
  is_correct: boolean;
}

export interface AdminQuestionInput {
  category: "B";
  topic: string;
  prompt: string;
  short_explanation: string;
  difficulty: number;
  is_sign_question: boolean;
  rule_codes: string[];
  media_id: string | null;
  options: AdminOptionInput[];
}

export interface AdminVersionOut {
  id: string;
  question_id: string;
  version: number;
  status: string;
  media_id: string | null;
}

export interface QaCheck {
  key: string;
  passed: boolean;
  detail: string;
}

export interface QaPayload {
  question: Record<string, unknown>;
  version: Record<string, unknown>;
  checklist: QaCheck[];
  all_passed: boolean;
  open_reports: number;
  practice_preview: {
    prompt: string;
    short_explanation: string;
    correct_option_id: string | null;
    options: Array<{ id: string; position: number; text: string; is_correct: boolean; explanation: string }>;
    rules: Array<{ code: string; text: string; superseded: boolean }>;
  };
  exam_preview: {
    prompt: string;
    options: Array<{ id: string; position: number; text: string }>;
  };
}

export interface AdminReport {
  id: string;
  question_version_id: string;
  reason: string;
  note: string | null;
  status: string;
  created_at: string | null;
}

export interface MediaOut {
  id: string;
  content_hash: string;
  content_type: string;
  media_type: string;
  url: string;
}

// ---- Slice 4: readiness / dashboard / ranking / mistakes ----
export interface RemainingTopic {
  topic: string;
  label: string;
  answered: number;
  needed: number;
}

export interface WeakTopic {
  topic: string;
  label: string;
  answered: number;
  mastery: number;
  needs_more_practice: boolean;
}

export interface ReadinessComponent {
  value: number;
  weight: number;
  [k: string]: unknown;
}

export interface ReadinessOut {
  state: "insufficient_data" | "initial" | "ready_estimate";
  label: string;
  score: number | null;
  exam_ready: boolean;
  unique_questions_attempted: number;
  mocks_completed: number;
  coverage_met: boolean;
  remaining_coverage: RemainingTopic[];
  components: {
    mock_performance: ReadinessComponent;
    topic_mastery: ReadinessComponent;
    mistake_recovery: ReadinessComponent;
    consistency_recency: ReadinessComponent;
  };
  weak_topics: WeakTopic[];
}

export interface DashboardOut {
  readiness: {
    state: string;
    label: string;
    score: number | null;
    exam_ready: boolean;
    coverage_met: boolean;
    remaining_coverage: RemainingTopic[];
  };
  weak_topics: WeakTopic[];
  recent_mocks: Array<{
    id: string;
    correct_count: number | null;
    question_count: number;
    passed: boolean | null;
    completed_at: string | null;
  }>;
  daily_goal: { goal: number | null; answered_today: number; met: boolean };
  streak: { current: number; longest: number };
  mistakes_open: number;
  ranking: { week: number; month: number; all: number };
}

export interface MistakeItem {
  question_id: string;
  topic: string | null;
  prompt: string;
  miss_count: number;
  last_missed_at: string | null;
  resolved: boolean;
}

export interface RankingRow {
  position: number;
  user_id?: string;
  name: string;
  points: number;
  is_self: boolean;
  show_on_ranking?: boolean;
}

export interface RankingOut {
  range: "week" | "month" | "all";
  entries: RankingRow[];
  own: RankingRow;
}

// ---- Theory / YHQ Handbook (docs/spec/14, 15) ----
export interface TheorySectionCard {
  id: string;
  slug: string;
  topic: string | null;
  icon_url: string | null;
  title: string;
  subtitle: string;
  article_count: number;
  progress?: { viewed: number; total: number };
}

export interface TheoryArticleCard {
  id: string;
  slug: string;
  kind: string;
  title: string;
  summary: string;
  progress_state?: string;
}

export interface TheoryRule {
  code: string;
  title: string | null;
  text: string;
  source_url: string;
  status: string;
  rule_version: number;
}

export interface TheoryBlock {
  id: string;
  type: string;
  position: number;
  body: string;
  data: Record<string, unknown> | null;
  media_url: string | null;
  media: MediaMeta | null;
  rule?: TheoryRule;
  ref_question_id?: string;
}

export interface TheoryArticle {
  id: string;
  slug: string;
  kind: string;
  section_id: string;
  version: number;
  hero_url: string | null;
  title: string;
  summary: string;
  blocks: TheoryBlock[];
  rules: TheoryRule[];
  linked_question_count: number;
  progress_state?: string;
}

export interface TheorySection extends TheorySectionCard {
  articles: TheoryArticleCard[];
}

export interface SignCard {
  id: string;
  code: string;
  family: string;
  name: string;
  media_url: string | null;
}

export interface SignDetail extends SignCard {
  meaning: string;
  driver_action: string;
  important: string | null;
  exam_trap: string | null;
  memory_tip: string | null;
  rules: TheoryRule[];
  linked_question_count: number;
  progress_state?: string;
}

export interface MarkingCard { id: string; code: string | null; group: string; name: string; media_url: string | null; }
export interface MarkingDetail extends MarkingCard {
  meaning: string; can_cross: string | null; can_stop_park: string | null;
  conflict_rule: string | null; exam_trap: string | null; memory_tip: string | null; rules: TheoryRule[];
}
export interface GestureCard { id: string; code: string | null; name: string; media_url: string | null; animation_url: string | null; }
export interface GestureDetail extends GestureCard {
  position_desc: string; allowed: string; forbidden: string; memory_tip: string | null; rules: TheoryRule[];
}
export interface LightCard { id: string; kind: string; title: string; media_url: string | null; }
export interface LightDetail extends LightCard {
  meaning: string; movement_permitted: string | null; direction_permitted: string | null;
  exceptions: string | null; typical_exam_situation: string | null; rules: TheoryRule[];
}

export interface SearchResult {
  type: "section" | "article" | "sign" | "marking" | "gesture" | "light" | "rule";
  id: string;
  slug?: string;
  code?: string;
  family?: string;
  title: string;
  subtitle: string;
}

export interface FavoriteItem {
  id: string;
  target_type: string;
  target_id: string;
  created_at: string | null;
}

export interface TheoryPracticeStart {
  session_id: string;
  source: string;
  target_type: string;
  target_id: string;
  questions_total: number;
  questions: NextQuestion[];
}

// ---- Home hub / next-action / topic progress (docs/spec/16, 17) ----
export interface NextAction {
  action: "resume_mock" | "mistakes" | "weak_topic" | "coverage" | "personalized";
  source: "mistakes" | "topic" | "personalized" | null;
  topic: string | null;
  topic_label: string | null;
  attempt_id: string | null;
  label: string;
  reason: string;
}

export interface HomeSummary {
  display_name: string;
  exam_countdown: { target_exam_date: string; days_remaining: number; passed: boolean } | null;
  readiness: {
    state: "insufficient_data" | "initial" | "ready_estimate";
    label: string;
    score: number | null;
    exam_ready: boolean;
    coverage_met: boolean;
    mocks_completed: number;
    unique_questions_attempted: number;
  };
  last_mock: {
    id: string; correct_count: number | null; question_count: number;
    passed: boolean | null; completed_at: string | null;
  } | null;
  daily_goal: { goal: number | null; answered_today: number; met: boolean };
  streak: { current: number; longest: number };
  recommendations: {
    weak_topic: { topic: string; label: string; mastery: number; answered: number } | null;
    mistakes_open: number;
  };
  ranking: {
    week: { points: number; position: number | null };
    all: { points: number; position: number | null };
  };
  next_action: NextAction;
}

export interface TopicProgressRow {
  topic: string;
  label: string;
  answered: number;
  correct: number;
  questions_seen: number;
  accuracy: number;
  mastery: number;
  needs_more_practice: boolean;
}

export interface FullProfileOut {
  display_name: string | null;
  ranking_name: string | null;
  show_on_ranking: boolean;
  category: string;
  language: string;
  target_exam_date: string | null;
  daily_goal: number | null;
  timezone: string;
  onboarding_completed: boolean;
}
