import { GitCompareArrows, Loader2 } from "lucide-react";

type Props = {
  count: number;
  onCompare: () => void;
  loading?: boolean;
};

export default function CompareBar({ count, onCompare, loading }: Props) {
  return (
    <div className="sticky bottom-0 left-0 right-0 z-10 border-t border-border bg-white/90 backdrop-blur px-4 py-2.5 flex items-center justify-between gap-3 shadow-[0_-2px_8px_rgba(0,0,0,0.06)]">
      <span className="text-[13px] text-ink-soft">
        <span className="font-semibold text-ink">{count}</span>{" "}
        course{count !== 1 ? "s" : ""} selected
      </span>
      <button
        type="button"
        onClick={onCompare}
        disabled={loading}
        className="btn-primary text-[12px] px-4 py-1.5 gap-1.5"
      >
        {loading ? (
          <>
            <Loader2 size={13} className="animate-spin" />
            Comparing…
          </>
        ) : (
          <>
            <GitCompareArrows size={13} />
            Compare →
          </>
        )}
      </button>
    </div>
  );
}
