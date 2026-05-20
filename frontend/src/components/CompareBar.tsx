import { ArrowRight, Loader2, X } from "lucide-react";

type Props = {
  count: number;
  onCompare: () => void;
  onClear: () => void;
  loading?: boolean;
};

const MAX = 3;

export default function CompareBar({ count, onCompare, onClear, loading }: Props) {
  const canCompare = count >= 2 && count <= MAX;
  const tooltip = count < 2 ? "Pick at least 2 to compare" : count > MAX ? "Max 3 to compare" : undefined;

  return (
    <div
      role="region"
      aria-label="Comparison selection"
      className={
        "sticky bottom-0 left-0 right-0 z-10 bg-white border-t border-border px-4 py-3 " +
        "flex items-center justify-between gap-3 shadow-bar transition-transform duration-200 " +
        (count === 0 ? "translate-y-full" : "translate-y-0")
      }
    >
      <div className="flex items-center gap-3">
        <span className="text-sm text-ink font-medium">{count} of {MAX} selected</span>
        <button
          type="button"
          onClick={onClear}
          aria-label="Clear comparison selection"
          className="flex items-center gap-1 text-sm text-ink-soft hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded"
        >
          <X size={14} /> Clear
        </button>
      </div>
      <button
        type="button"
        onClick={onCompare}
        disabled={!canCompare || loading}
        title={tooltip}
        aria-label="Compare selected courses"
        className={
          "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors " +
          "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 " +
          (canCompare
            ? "bg-primary text-white hover:bg-primary-dark"
            : "bg-pill text-primary/50 cursor-not-allowed")
        }
      >
        {loading ? (
          <>
            <Loader2 size={16} className="animate-spin" /> Comparing
          </>
        ) : (
          <>
            Compare <ArrowRight size={16} />
          </>
        )}
      </button>
    </div>
  );
}
