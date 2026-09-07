// Browse-only admin media library (docs/spec/08). Grid + search + media-type filter +
// load-more pagination (limit/offset), opening a metadata detail sheet. NO delete in this
// cycle — the orphan-cleanup cron owns deletion. Server-side role gating is authoritative.
// All copy is Uzbek Latin; content-addressed URLs only; values render as React text nodes.
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { adminApi } from "../api";
import { t } from "../i18n/uz";
import type { MediaListItem } from "../types";
import {
  Badge,
  BottomSheet,
  Button,
  Chip,
  EmptyState,
  QuestionMedia,
  Skeleton
} from "../ui/components";

type TypeFilter = "" | "image" | "gif" | "video";

const PAGE_LIMIT = 24;

const TYPE_FILTERS: Array<[TypeFilter, string]> = [
  ["", t("mediaFilterAll")],
  ["image", t("mediaFilterImage")],
  ["gif", t("mediaFilterGif")],
  ["video", t("mediaFilterVideo")]
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function MediaThumb({ item }: { item: MediaListItem }) {
  if (item.media_type === "video") {
    return (
      <video className="media-tile__media" src={item.url} muted playsInline preload="metadata"
        aria-label={item.alt ?? "video"} />
    );
  }
  return <img className="media-tile__media" src={item.url} alt={item.alt ?? ""} loading="lazy" />;
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="media-detail__row">
      <span className="muted">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function MediaDetail({ item, onClose }: { item: MediaListItem; onClose: () => void }) {
  const dims = item.width && item.height ? `${item.width} × ${item.height}` : "—";
  const dur = item.duration_ms != null ? `${(item.duration_ms / 1000).toFixed(1)} s` : "—";
  return (
    <BottomSheet onClose={onClose}>
      <div className="media-detail">
        <div className="media-picker__head">
          <h2 className="media-picker__title">{item.alt ?? item.content_type}</h2>
          <Button variant="ghost" onClick={onClose}>{t("mediaClose")}</Button>
        </div>
        <QuestionMedia url={item.url} mediaType={item.media_type} alt={item.alt ?? ""} />
        <div className="media-detail__meta">
          <DetailRow label={t("mediaDetailType")} value={item.content_type} />
          <DetailRow label={t("mediaDetailSize")} value={formatBytes(item.byte_size)} />
          <DetailRow label={t("mediaDetailDimensions")} value={dims} />
          <DetailRow label={t("mediaDetailDuration")} value={dur} />
          <DetailRow
            label={t("inUse")}
            value={<Badge tone={item.in_use ? "success" : undefined}>{item.in_use ? t("inUse") : t("notUsed")}</Badge>}
          />
          <DetailRow label={t("mediaDetailHash")} value={<code className="media-detail__hash">{item.content_hash}</code>} />
          <DetailRow
            label={t("mediaDetailCreated")}
            value={item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
          />
        </div>
      </div>
    </BottomSheet>
  );
}

export function MediaLibrary() {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("");
  const [items, setItems] = useState<MediaListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<MediaListItem | null>(null);
  const firstLoad = useRef(true);

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
        firstLoad.current = false;
      }
    },
    [debounced, typeFilter]
  );

  useEffect(() => {
    void load(0, false);
  }, [load]);

  const canLoadMore = items.length < total;

  return (
    <div className="admin-page media-library">
      <h2>{t("mediaLibrary")}</h2>
      <p className="muted">{t("mediaLibraryHint")} · {total}</p>

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
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} height={96} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState message={t("mediaEmpty")} />
      ) : (
        <>
          <div className="media-grid">
            {items.map((item) => (
              <button key={item.id} type="button" className="media-tile"
                title={item.alt ?? item.content_type} onClick={() => setSelected(item)}>
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

      {selected && <MediaDetail item={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
