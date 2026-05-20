import { ArrowRight, AlertTriangle, Check, MessageCircle, GripVertical, GitCompareArrows } from "lucide-react";
import type { Recommendation } from "../lib/api";
import type { AttachedCourse } from "./CourseChip";

type Props = {
  rec: Recommendation;
  onAskAbout: (course: AttachedCourse) => void;
  selected?: boolean;
  onToggleCompare: () => void;
  compareDisabled?: boolean;
};

function initials(provider: string | null): string {
  if (!provider) return "uG";
  const words = provider.replace(/[^a-zA-Z ]/g, "").trim().split(/\s+/);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

export default function CourseCard({ rec, onAskAbout, selected, onToggleCompare, compareDisabled }: Props) {
  const chips = [rec.duration_label, rec.format, rec.level, rec.fee_bucket].filter(Boolean) as string[];
  const reasons = rec.fit_reasons && rec.fit_reasons.length > 0 ? rec.fit_reasons : [rec.why_this_fits];

  const attachedCourse: AttachedCourse = {
    slug: rec.course_slug,
    title: rec.title,
    provider: rec.provider,
  };

  const handleDragStart = (e: React.DragEvent<HTMLDivElement>) => {
    e.dataTransfer.setData(
      "application/upgrad-course",
      JSON.stringify(attachedCourse)
    );
    e.dataTransfer.effectAllowed = "copy";
  };

  const handleAskAbout = () => {
    onAskAbout(attachedCourse);
  };

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      className="group relative flex flex-col rounded-2xl border border-border bg-white p-5 shadow-md hover:shadow-xl hover:-translate-y-1 transition-all duration-200 slide-up cursor-grab active:cursor-grabbing"
    >
      {/* Drag handle */}
      <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-40 transition-opacity text-ink-soft">
        <GripVertical size={16} />
      </div>

      <div className="flex items-center gap-3 mb-3">
        <div className="flex items-center justify-center w-11 h-11 rounded-full border border-border bg-surface text-primary-dark font-semibold text-sm shrink-0">
          {initials(rec.provider)}
        </div>
        <div className="min-w-0">
          <div className="text-[12px] text-ink-soft truncate">{rec.provider || "upGrad"}</div>
          {rec.programme_type && (
            <div className="text-[11px] uppercase tracking-wider text-ink-soft truncate">
              {rec.programme_type}
            </div>
          )}
        </div>
      </div>

      <h3 className="text-[17px] font-semibold text-ink leading-snug mb-3 line-clamp-2">
        {rec.title}
      </h3>

      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {chips.map((c) => (
            <span key={c} className="chip">
              {c}
            </span>
          ))}
        </div>
      )}

      <div className="text-[12px] font-semibold text-ink mb-2">Why this fits you</div>
      <ul className="space-y-1.5 mb-3">
        {reasons.map((r, i) => (
          <li key={i} className="flex gap-2 text-[13px] text-ink-soft leading-snug">
            <Check size={15} className="text-success shrink-0 mt-0.5" />
            <span>{r}</span>
          </li>
        ))}
      </ul>

      {rec.watch_outs && (
        <div className="flex gap-2 text-[12px] text-ink-soft leading-snug mb-3 bg-surface rounded-md px-3 py-2">
          <AlertTriangle size={14} className="text-primary shrink-0 mt-0.5" />
          <span>{rec.watch_outs}</span>
        </div>
      )}

      {rec.faculty && rec.faculty.length > 0 && (
        <div className="text-[12px] text-ink-soft mb-4 leading-snug">
          <span className="font-medium text-ink">Faculty:</span>{" "}
          {rec.faculty.slice(0, 3).map((f) => f.name).join(", ")}
        </div>
      )}

      {/* Actions row */}
      <div className="mt-auto flex gap-2">
        <a
          href={rec.course_url}
          target="_blank"
          rel="noreferrer noopener"
          className="btn-primary flex-1"
        >
          View course <ArrowRight size={16} />
        </a>

        <button
          type="button"
          onClick={handleAskAbout}
          title="Ask about this course"
          className="btn-ghost border border-border rounded-md px-2.5 py-2 shrink-0"
        >
          <MessageCircle size={15} />
        </button>

        <button
          type="button"
          onClick={onToggleCompare}
          disabled={compareDisabled}
          title={compareDisabled ? "Max 3 to compare" : selected ? "Remove from compare" : "Add to compare"}
          className={
            "border rounded-md px-2.5 py-2 shrink-0 text-[11px] font-medium transition-colors " +
            (selected
              ? "bg-primary text-white border-primary"
              : "btn-ghost border-border " + (compareDisabled ? "opacity-40 cursor-not-allowed" : ""))
          }
        >
          <GitCompareArrows size={15} />
        </button>
      </div>
    </div>
  );
}
