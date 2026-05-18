import { useEffect, useRef, useState, type KeyboardEvent } from "react";

type Props = {
  onSend: (text: string) => void;
  disabled?: boolean;
};

export default function Composer({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!disabled) taRef.current?.focus();
  }, [disabled]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    requestAnimationFrame(() => taRef.current?.focus());
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-border bg-white px-4 py-3">
      <div className="max-w-3xl mx-auto flex items-end gap-2">
        <textarea
          ref={taRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKey}
          rows={1}
          autoFocus
          placeholder="say something..."
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
      <div className="max-w-3xl mx-auto mt-1.5 text-[11px] text-ink-soft px-1">
        Enter to send, Shift+Enter for newline
      </div>
    </div>
  );
}
