import { useEffect, useRef } from "react";
import { Loader2, Sparkles } from "lucide-react";
import CourseCard from "./CourseCard";
import CompareBar from "./CompareBar";
import type { Recommendation } from "../lib/api";
import type { AttachedCourse } from "./CourseChip";

type Props = {
  items: Recommendation[];
  onSeeMore: () => void;
  loadingMore: boolean;
  exhausted: boolean;
  selectedSlugs: string[];
  onToggleCompare: (slug: string) => void;
  onCompare: () => void;
  comparingLoading?: boolean;
  onAskAbout: (course: AttachedCourse) => void;
};

const MAX_COMPARE = 3;
const NEW_CARD_TTL_MS = 2000;

export default function PicksRail({
  items,
  onSeeMore,
  loadingMore,
  exhausted,
  selectedSlugs,
  onToggleCompare,
  onCompare,
  comparingLoading,
  onAskAbout,
}: Props) {
  const scrollContainerRef = useRef<HTMLElement | null>(null);
  const lastUserScrollAt = useRef<number>(0);
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const glowTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Track manual scroll
  const handleScroll = () => {
    lastUserScrollAt.current = Date.now();
  };

  // Auto-scroll to first new card when items change
  useEffect(() => {
    const now = Date.now();
    // Don't fight the user if they scrolled in the last second
    if (now - lastUserScrollAt.current < 1000) return;

    // Find first "new" card (addedAt within last 2s)
    const newCard = items.find(
      (r) => r.addedAt !== undefined && now - (r.addedAt as number) < NEW_CARD_TTL_MS
    );
    if (!newCard) return;

    const node = cardRefs.current.get(newCard.course_slug);
    if (!node) return;

    // Apply glow
    node.setAttribute("data-new", "true");
    const existing = glowTimers.current.get(newCard.course_slug);
    if (existing) clearTimeout(existing);
    glowTimers.current.set(
      newCard.course_slug,
      setTimeout(() => {
        node.removeAttribute("data-new");
        glowTimers.current.delete(newCard.course_slug);
      }, NEW_CARD_TTL_MS)
    );

    // Scroll with a small header offset
    setTimeout(() => {
      node.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  }, [items.length]);

  return (
    <aside
      ref={scrollContainerRef as React.RefObject<HTMLElement>}
      onScroll={handleScroll}
      className="flex flex-col h-full overflow-y-auto px-4 py-6 relative"
    >
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={16} className="text-primary" />
        <h2 className="text-sm font-semibold text-ink">Your picks</h2>
        {items.length > 0 && (
          <span className="text-[12px] text-ink-soft">({items.length})</span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-center">
          <p className="text-[13px] text-ink-soft leading-relaxed max-w-[220px]">
            Your matches will show up here once I know a little about you.
          </p>
        </div>
      ) : (
        <div className="space-y-3 pb-14">
          {items.map((rec) => (
            <div
              key={rec.course_slug}
              ref={(el) => {
                if (el) cardRefs.current.set(rec.course_slug, el);
                else cardRefs.current.delete(rec.course_slug);
              }}
            >
              <CourseCard
                rec={rec}
                onAskAbout={onAskAbout}
                selected={selectedSlugs.includes(rec.course_slug)}
                onToggleCompare={() => onToggleCompare(rec.course_slug)}
                compareDisabled={
                  !selectedSlugs.includes(rec.course_slug) &&
                  selectedSlugs.length >= MAX_COMPARE
                }
              />
            </div>
          ))}

          {!exhausted && (
            <button
              type="button"
              onClick={onSeeMore}
              disabled={loadingMore}
              className="btn-ghost w-full border border-border rounded-xl py-2.5"
            >
              {loadingMore ? (
                <>
                  <Loader2 size={15} className="animate-spin" /> Finding more
                </>
              ) : (
                "See 3 more matches"
              )}
            </button>
          )}
        </div>
      )}

      {/* CompareBar — sticky at bottom when ≥2 selected */}
      {selectedSlugs.length >= 2 && (
        <CompareBar
          count={selectedSlugs.length}
          onCompare={onCompare}
          loading={comparingLoading}
        />
      )}
    </aside>
  );
}
