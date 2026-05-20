import { CheckCircle2 } from "lucide-react";

type Props = {
  filled: number;
  total: number;
};

export default function Progress({ filled, total }: Props) {
  if (total <= 0) return null;
  const pct = Math.min(100, Math.round((filled / total) * 100));
  const done = filled >= total;
  return (
    <div
      className="border-b border-border bg-white px-6 py-2"
      title={`I need a few essentials to recommend well. We're ${filled} of ${total} in.`}
    >
      <div className="max-w-[1280px] mx-auto">
        {done ? (
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} className="text-success shrink-0" />
            <span className="text-xs font-medium text-success whitespace-nowrap">
              Ready to recommend
            </span>
          </div>
        ) : (
          <>
            <div className="text-xs font-medium text-ink-soft mb-1">
              {filled} of {total} essentials
            </div>
            <div className="h-1 rounded-full bg-surface-alt overflow-hidden">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${pct}%`, transition: "width 400ms ease" }}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
