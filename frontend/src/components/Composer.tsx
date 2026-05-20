import { useEffect, useRef, useState, type KeyboardEvent, type DragEvent } from "react";
import CourseChip, { type AttachedCourse } from "./CourseChip";

type Props = {
  onSend: (text: string, attachedCourse?: AttachedCourse) => void;
  disabled?: boolean;
  attachedCourse?: AttachedCourse | null;
  courseMessageCount?: number;
  onDismissCourse?: () => void;
  onDropCourse?: (course: AttachedCourse) => void;
};

export default function Composer({
  onSend,
  disabled,
  attachedCourse,
  courseMessageCount,
  onDismissCourse,
  onDropCourse,
}: Props) {
  const [value, setValue] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!disabled) taRef.current?.focus();
  }, [disabled]);

  // Focus input when a course is attached (from "Ask about this" click)
  useEffect(() => {
    if (attachedCourse) {
      requestAnimationFrame(() => taRef.current?.focus());
    }
  }, [attachedCourse?.slug]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, attachedCourse ?? undefined);
    setValue("");
    requestAnimationFrame(() => taRef.current?.focus());
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    if (e.dataTransfer.types.includes("application/upgrad-course")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      setIsDragOver(true);
    }
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    const raw = e.dataTransfer.getData("application/upgrad-course");
    if (!raw) return;
    try {
      const course = JSON.parse(raw) as AttachedCourse;
      onDropCourse?.(course);
    } catch {}
  };

  return (
    <div
      className={
        "border-t border-border bg-white px-4 py-3 transition-all duration-200 " +
        (isDragOver ? "ring-2 ring-primary border-dashed bg-pill/40" : "")
      }
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDragOver && (
        <div className="text-[12px] text-primary font-medium text-center mb-2 fade-in">
          Drop course here to ask about it
        </div>
      )}

      <div className="max-w-3xl mx-auto flex flex-col gap-2">
        {attachedCourse && (
          <CourseChip
            course={attachedCourse}
            onDismiss={onDismissCourse ?? (() => {})}
            messageCount={courseMessageCount}
          />
        )}

        <div className="flex items-end gap-2">
          <textarea
            ref={taRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKey}
            rows={1}
            autoFocus
            placeholder={
              attachedCourse
                ? `Ask about ${attachedCourse.title}…`
                : "say something..."
            }
            disabled={disabled}
            className="flex-1 resize-none rounded-xl border border-border bg-white px-4 py-2.5 text-[15px] text-ink placeholder:text-ink-soft focus:outline-none focus:border-primary focus:ring-2 focus:ring-pill disabled:opacity-50 max-h-32 transition-colors"
          />
          <button
            type="button"
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="btn-primary px-5"
          >
            Send
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto mt-1.5 text-[11px] text-ink-soft px-1">
        Enter to send, Shift+Enter for newline
      </div>
    </div>
  );
}
