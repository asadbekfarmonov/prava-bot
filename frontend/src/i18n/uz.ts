// Single UI string catalog (Uzbek Latin). Russian (v2) adds a parallel catalog.
export const uz = {
  appTitle: "prava-bot",
  tagline: "YHQ nazariy imtihoniga tayyorgarlik",
  signInTelegram: "Telegram orqali kirish",
  devLogin: "Dev rejimida kirish",
  openFromTelegram: "Iltimos, ilovani Telegram orqali oching",
  onboardingTitle: "Ro'yxatdan o'tish",
  displayName: "Ismingiz",
  save: "Saqlash",
  startPractice: "Mashqni boshlash",
  loading: "Yuklanmoqda...",
  submit: "Javob berish",
  next: "Keyingi savol",
  correct: "To'g'ri!",
  incorrect: "Noto'g'ri",
  yourAnswer: "Sizning javobingiz",
  correctAnswer: "To'g'ri javob",
  rule: "Qoida",
  rememberThis: "Eslab qoling",
  noQuestions: "Bu mavzuda savol topilmadi",
  errorGeneric: "Xatolik yuz berdi",
  topicAll: "Aralash (barcha mavzular)"
};
export type Dict = typeof uz;
export function t(key: keyof Dict): string {
  return uz[key];
}
