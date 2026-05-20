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
      className="border-b border-border bg-white/70 backdrop-blur px-5 py-2.5"
      title={`I need a few essentials to recommend well. We're ${filled} of ${total} in.`}
    >
      <div className="max-w-[1280px] mx-auto flex items-center gap-3">
        <span className="text-[12px] font-medium text-ink-soft whitespace-nowrap">
          {done ? "Ready to recommend" : `${filled} of ${total} essentials`}
        </span>
        <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
          <div
            className="h-full rounded-full bg-primary"
            style={{ width: `${pct}%`, transition: "width 400ms ease" }}
          />
        </div>
      </div>
    </div>
  );
}
