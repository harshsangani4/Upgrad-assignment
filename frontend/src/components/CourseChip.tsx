import { X, Paperclip } from "lucide-react";

export type AttachedCourse = {
  slug: string;
  title: string;
  provider: string | null;
  logoUrl?: string | null;
};

type Props = {
  course: AttachedCourse;
  onDismiss: () => void;
  messageCount?: number;
};

function initials(provider: string | null): string {
  if (!provider) return "uG";
  const words = provider.replace(/[^a-zA-Z ]/g, "").trim().split(/\s+/);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

export default function CourseChip({ course, onDismiss, messageCount }: Props) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl border border-primary/30 bg-pill/60 backdrop-blur-sm">
        <Paperclip size={13} className="text-primary shrink-0" />

        {course.logoUrl ? (
          <img
            src={course.logoUrl}
            alt={course.provider || ""}
            className="w-5 h-5 rounded-full object-contain shrink-0"
          />
        ) : (
          <span className="w-5 h-5 rounded-full bg-primary/10 text-primary text-[9px] font-bold flex items-center justify-center shrink-0">
            {initials(course.provider)}
          </span>
        )}

        <span className="text-[12px] text-ink font-medium flex-1 truncate min-w-0">
          Re:{" "}
          <span className="font-semibold">{course.title}</span>
          {course.provider && (
            <span className="text-ink-soft font-normal"> ({course.provider})</span>
          )}
        </span>

        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss course"
          className="shrink-0 text-ink-soft hover:text-primary transition-colors p-0.5 rounded"
        >
          <X size={13} />
        </button>
      </div>

      {messageCount !== undefined && messageCount > 0 && (
        <p className="text-[11px] text-ink-soft px-3">
          Still on this course — dismiss to go back.
          {messageCount >= 2 && " (auto-clears after 3 messages)"}
        </p>
      )}
    </div>
  );
}
