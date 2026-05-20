import { Loader2, Sparkles } from "lucide-react";
import CourseCard from "./CourseCard";
import type { Recommendation } from "../lib/api";

type Props = {
  items: Recommendation[];
  onSeeMore: () => void;
  loadingMore: boolean;
  exhausted: boolean;
};

export default function PicksRail({ items, onSeeMore, loadingMore, exhausted }: Props) {
  return (
    <aside className="flex flex-col h-full overflow-y-auto px-4 py-6">
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
        <div className="space-y-3">
          {items.map((rec) => (
            <CourseCard key={rec.course_slug} rec={rec} />
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
    </aside>
  );
}
