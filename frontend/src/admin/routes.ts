// Locked Admin information architecture (docs/spec/20 §1). Route-stack model, NO React Router.
export type AdminTab = "dashboard" | "questions" | "assessments" | "theory" | "more";

export type AdminRoute =
  | { kind: "tab"; tab: AdminTab }
  | { kind: "question"; id: string }
  | { kind: "question-new" }
  | { kind: "question-preview"; id: string }
  | { kind: "question-qa"; id: string }
  | { kind: "assessment"; id: string }
  | { kind: "assessment-new" }
  | { kind: "theory-hub" }
  | { kind: "theory-section"; id: string }
  | { kind: "theory-article"; id: string }
  | { kind: "theory-article-new" }
  | { kind: "sign"; id: string }
  | { kind: "sign-new" }
  | { kind: "marking"; id: string }
  | { kind: "marking-new" }
  | { kind: "gesture"; id: string }
  | { kind: "gesture-new" }
  | { kind: "light"; id: string }
  | { kind: "light-new" }
  | { kind: "admin-search" }
  | { kind: "review" }
  | { kind: "reports" }
  | { kind: "rules" }
  | { kind: "rule"; id: string }
  | { kind: "media" }
  | { kind: "admins" }
  | { kind: "audit" }
  | { kind: "imports" };

export const ADMIN_TABS: { tab: AdminTab; label: string }[] = [
  { tab: "dashboard", label: "Panel" },
  { tab: "questions", label: "Savollar" },
  { tab: "assessments", label: "Testlar" },
  { tab: "theory", label: "Nazariya" },
  { tab: "more", label: "Ko'proq" }
];

// Which primary tab "owns" a given nested route (drives active bottom-nav highlight).
export function tabForRoute(route: AdminRoute): AdminTab {
  switch (route.kind) {
    case "tab":
      return route.tab;
    case "question":
    case "question-new":
    case "question-preview":
    case "question-qa":
      return "questions";
    case "assessment":
    case "assessment-new":
      return "assessments";
    case "theory-hub":
    case "theory-section":
    case "theory-article":
    case "theory-article-new":
    case "sign":
    case "sign-new":
    case "marking":
    case "marking-new":
    case "gesture":
    case "gesture-new":
    case "light":
    case "light-new":
      return "theory";
    default:
      return "more";
  }
}
