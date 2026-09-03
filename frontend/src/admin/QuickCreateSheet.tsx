// Quick-create bottom sheet (docs/spec/20 §4). Exactly these items, role-hidden.
export type QuickCreateKind =
  | "question" | "assessment" | "article" | "sign" | "marking" | "gesture" | "light" | "rule";

const ITEMS: { kind: QuickCreateKind; label: string; minRole: "author" | "admin" }[] = [
  { kind: "question", label: "Savol", minRole: "author" },
  { kind: "assessment", label: "Test", minRole: "author" },
  { kind: "article", label: "Nazariya maqolasi", minRole: "author" },
  { kind: "sign", label: "Yo'l belgisi", minRole: "author" },
  { kind: "marking", label: "Yo'l chizig'i", minRole: "author" },
  { kind: "gesture", label: "Regulirovshchik ishorasi", minRole: "author" },
  { kind: "light", label: "Svetofor holati", minRole: "author" },
  { kind: "rule", label: "Qoida", minRole: "admin" }
];

export function QuickCreateSheet({
  open,
  isAdmin,
  onPick,
  onClose
}: {
  open: boolean;
  isAdmin: boolean;
  onPick: (kind: QuickCreateKind) => void;
  onClose: () => void;
}) {
  if (!open) return null;
  const items = ITEMS.filter((i) => i.minRole !== "admin" || isAdmin);
  return (
    <div className="admin-sheet-backdrop" onClick={onClose}>
      <div className="admin-sheet" role="dialog" aria-label="Yangi yaratish" onClick={(e) => e.stopPropagation()}>
        <div className="admin-sheet__handle" />
        <h2 className="admin-sheet__title">Yangi yaratish</h2>
        {items.map((i) => (
          <button key={i.kind} type="button" className="admin-sheet__item" onClick={() => onPick(i.kind)}>
            {i.label}
          </button>
        ))}
        <button type="button" className="admin-sheet__cancel" onClick={onClose}>Bekor qilish</button>
      </div>
    </div>
  );
}
