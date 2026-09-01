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
