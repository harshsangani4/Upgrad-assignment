import { useState } from "react";
import {
  ArrowRight,
  AlertTriangle,
  Check,
  GripVertical,
  MessageCircle,
  Bookmark,
  BookmarkCheck,
} from "lucide-react";
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
  const [saved, setSaved] = useState(false);
  const chips = [rec.duration_label, rec.format, rec.level, rec.fee_bucket].filter(Boolean) as string[];
  const reasons = rec.fit_reasons && rec.fit_reasons.length > 0 ? rec.fit_reasons : [rec.why_this_fits];

  const attachedCourse: AttachedCourse = {
    slug: rec.course_slug,
    title: rec.title,
    provider: rec.provider,
  };

  const handleDragStart = (e: React.DragEvent<HTMLButtonElement>) => {
    e.dataTransfer.setData("application/upgrad-course", JSON.stringify(attachedCourse));
    e.dataTransfer.effectAllowed = "copy";
  };

  const cardClass = [
    "flex flex-col rounded-lg border bg-white p-6 transition-all",
    selected
      ? "ring-2 ring-primary border-primary"
      : "border-border shadow-md hover:shadow-xl hover:-translate-y-1",
  ].join(" ");

  return (
    <div className={`${cardClass} slide-up`}>
      {/* Header row */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          draggable
          onDragStart={handleDragStart}
          aria-label="Drag this course into the chat to ask about it"
          title="Drag into chat to ask about this course"
          className="hidden md:flex w-7 h-7 items-center justify-center rounded-md border border-border-strong bg-white text-ink-soft cursor-grab active:cursor-grabbing hover:bg-pill hover:border-primary hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-colors shrink-0"
        >
          <GripVertical size={16} strokeWidth={2.25} />
        </button>

        <div className="flex items-center justify-center w-10 h-10 rounded-full border border-border bg-surface text-primary-dark font-semibold text-sm shrink-0">
          {initials(rec.provider)}
        </div>

        <div className="min-w-0 flex-1 text-sm text-ink-soft truncate">
          {rec.provider || "upGrad"}
          {rec.programme_type ? ` · ${rec.programme_type}` : ""}
        </div>

        <label className="flex items-center gap-2 cursor-pointer select-none shrink-0">
          <input
            type="checkbox"
            className="w-4 h-4 rounded border-2 border-border accent-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
            checked={!!selected}
            disabled={compareDisabled}
            onChange={onToggleCompare}
            aria-label="Select for comparison"
          />
          <span className="text-sm text-ink-soft">Compare</span>
        </label>
      </div>

      {/* Title */}
      <h3 className="mt-4 text-lg font-semibold text-ink leading-snug line-clamp-2">
        {rec.title}
      </h3>

      {/* Chips */}
      {chips.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {chips.map((c) => (
            <span key={c} className="chip">{c}</span>
          ))}
        </div>
      )}

      {/* Why this fits */}
      <div className="mt-6 text-sm font-semibold text-ink">Why this fits you</div>
      <ul className="mt-2 space-y-1.5">
        {reasons.map((r, i) => (
          <li key={i} className="flex gap-2 text-sm text-ink-soft leading-snug">
            <Check size={15} className="text-success shrink-0 mt-0.5" />
            <span>{r}</span>
          </li>
        ))}
      </ul>

      {/* Watch out */}
      {rec.watch_outs && (
        <div className="mt-3 flex gap-2 text-sm text-ink-soft leading-snug bg-surface rounded-md px-3 py-2">
          <AlertTriangle size={15} className="text-warning shrink-0 mt-0.5" />
          <span>{rec.watch_outs}</span>
        </div>
      )}

      {/* Faculty */}
      {rec.faculty && rec.faculty.length > 0 && (
        <div className="mt-3 text-sm text-ink-soft leading-snug">
          <span className="font-medium text-ink">Faculty:</span>{" "}
          {rec.faculty.slice(0, 3).map((f) => f.name).join(", ")}
        </div>
      )}

      {/* Actions row */}
      <div className="mt-6 flex flex-col sm:flex-row gap-2">
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
          onClick={() => setSaved((s) => !s)}
          aria-label={saved ? "Remove from saved" : "Save course"}
          className="btn-ghost border border-border"
        >
          {saved ? <BookmarkCheck size={15} className="text-primary" /> : <Bookmark size={15} />}
          {saved ? "Saved" : "Save"}
        </button>
        <button
          type="button"
          onClick={() => onAskAbout(attachedCourse)}
          aria-label="Ask about this course"
          className="btn-ghost border border-border"
        >
          <MessageCircle size={15} /> Ask
        </button>
      </div>
    </div>
  );
}
