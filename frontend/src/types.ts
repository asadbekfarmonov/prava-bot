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
