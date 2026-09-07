// Reusable media picker (docs/spec/05, 08). Rendered in a ui BottomSheet with two modes:
//   * "Mavjud media" — browse/search/filter already-uploaded media (adminApi.listMedia)
//     and pick a tile (so admins REUSE content-addressed media instead of re-uploading);
//   * "Yangi yuklash" — upload a fresh file via the existing adminApi.uploadMedia and
//     immediately select the returned media.
// Admin-gating is server-side (every /api/admin/* call is role-gated); this UI is only a
// convenience. All labels are Uzbek Latin; all values render as React text nodes.
import { useCallback, useEffect, useRef, useState } from "react";
import { adminApi } from "../api";
import { t } from "../i18n/uz";
import type { MediaListItem } from "../types";
import { Badge, BottomSheet, Button, Chip, EmptyState, Skeleton } from "../ui/components";

type Mode = "existing" | "upload";
type TypeFilter = "" | "image" | "gif" | "video";

export interface MediaPickerSelection {
  id: string;
  url: string;
  content_type: string;
}

const PAGE_LIMIT = 24;

const TYPE_FILTERS: Array<[TypeFilter, string]> = [
  ["", t("mediaFilterAll")],
  ["image", t("mediaFilterImage")],
  ["gif", t("mediaFilterGif")],
  ["video", t("mediaFilterVideo")]
];

function MediaThumb({ item }: { item: MediaListItem }) {
  if (item.media_type === "video") {
    return (
      <video className="media-tile__media" src={item.url} muted playsInline preload="metadata"
        aria-label={item.alt ?? "video"} />
    );
  }
  // image + gif
  return <img className="media-tile__media" src={item.url} alt={item.alt ?? ""} loading="lazy" />;
}

export function MediaPicker({
  open,
  onClose,
  onSelect,
  accept
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (media: MediaPickerSelection) => void;
  accept?: string;
}) {
  const [mode, setMode] = useState<Mode>("existing");
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("");
  const [items, setItems] = useState<MediaListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  // Debounce the search box (250ms) to avoid a request per keystroke.
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(query.trim()), 250);
    return () => window.clearTimeout(id);
  }, [query]);

  const load = useCallback(
    async (nextOffset: number, append: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const res = await adminApi.listMedia({
          q: debounced || undefined,
          media_type: typeFilter || undefined,
          limit: PAGE_LIMIT,
          offset: nextOffset
        });
        setTotal(res.total);
        setOffset(res.offset);
        setItems((prev) => (append ? [...prev, ...res.items] : res.items));
      } catch (e) {
        setError(String((e as Error).message) || t("mediaLoadFailed"));
      } finally {
        setLoading(false);
      }
    },
    [debounced, typeFilter]
  );

  // (Re)load the first page whenever the picker opens in "existing" mode or a filter changes.
  useEffect(() => {
    if (open && mode === "existing") {
      void load(0, false);
    }
  }, [open, mode, load]);

  async function handleUpload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const m = await adminApi.uploadMedia(file);
      onSelect({ id: m.id, url: m.url, content_type: m.content_type });
      onClose();
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  if (!open) return null;

  const canLoadMore = items.length < total;

  return (
    <BottomSheet onClose={onClose}>
      <div className="media-picker">
        <div className="media-picker__head">
          <h2 className="media-picker__title">{t("chooseMedia")}</h2>
          <Button variant="ghost" onClick={onClose}>{t("mediaClose")}</Button>
        </div>

        <div className="media-picker__modes" role="tablist">
          <Chip active={mode === "existing"} onClick={() => setMode("existing")}>{t("existingMedia")}</Chip>
          <Chip active={mode === "upload"} onClick={() => setMode("upload")}>{t("uploadNew")}</Chip>
        </div>

        {mode === "existing" ? (
          <>
            <input
              className="admin-searchfield"
              type="search"
              inputMode="search"
              value={query}
              placeholder={t("mediaSearchPlaceholder")}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="media-picker__filters">
              {TYPE_FILTERS.map(([value, label]) => (
                <Chip key={value || "all"} active={typeFilter === value} onClick={() => setTypeFilter(value)}>
                  {label}
                </Chip>
              ))}
            </div>

            {error && <p className="explain">{error}</p>}

            {loading && items.length === 0 ? (
              <div className="media-grid">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} height={96} />
                ))}
              </div>
            ) : items.length === 0 ? (
              <EmptyState message={t("mediaEmpty")} />
            ) : (
              <>
                <div className="media-grid">
                  {items.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="media-tile"
                      title={item.alt ?? item.content_type}
                      onClick={() => {
                        onSelect({ id: item.id, url: item.url, content_type: item.content_type });
                        onClose();
                      }}
                    >
                      <MediaThumb item={item} />
                      <span className="media-tile__badge">
                        <Badge tone={item.in_use ? "success" : undefined}>
                          {item.in_use ? t("inUse") : t("notUsed")}
                        </Badge>
                      </span>
                    </button>
                  ))}
                </div>
                {canLoadMore && (
                  <Button variant="secondary" block disabled={loading}
                    onClick={() => void load(offset + PAGE_LIMIT, true)}>
                    {loading ? t("loading") : t("mediaLoadMore")}
                  </Button>
                )}
              </>
            )}
          </>
        ) : (
          <div className="media-picker__upload">
            <p className="muted">{t("uploadNew")}</p>
            <input
              ref={fileRef}
              type="file"
              accept={accept}
              disabled={uploading}
              onChange={(e) => e.target.files && e.target.files[0] && handleUpload(e.target.files[0])}
            />
            {uploading && <p className="muted">{t("mediaUploading")}</p>}
            {error && <p className="explain">{error}</p>}
          </div>
        )}
      </div>
    </BottomSheet>
  );
}
