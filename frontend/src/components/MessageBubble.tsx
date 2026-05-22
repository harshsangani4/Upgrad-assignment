import { Paperclip } from "lucide-react";
import type { AttachedCourse } from "../lib/api";

type Props = {
  role: "user" | "assistant";
  content: string;
  attachedCourse?: AttachedCourse;
};

export default function MessageBubble({ role, content, attachedCourse }: Props) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} my-2 fade-in`}>
      <div
        className={
          isUser
            ? "max-w-[80%] rounded-2xl rounded-br-sm bg-primary text-white px-4 py-3 text-[15px] leading-relaxed whitespace-pre-wrap"
            : "max-w-[80%] rounded-2xl rounded-bl-sm bg-surface text-ink px-4 py-3 text-[15px] leading-relaxed whitespace-pre-wrap"
        }
      >
        {attachedCourse && (
          <div className="flex items-center gap-1.5 mb-2 rounded-md bg-white/15 px-2 py-1 text-xs font-medium">
            <Paperclip size={12} className="shrink-0" />
            <span className="truncate">{attachedCourse.title}</span>
          </div>
        )}
        {content || <TypingDots />}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex items-center py-1">
      <span className="typing-dot" style={{ animationDelay: "0s" }} />
      <span className="typing-dot" style={{ animationDelay: "0.15s" }} />
      <span className="typing-dot" style={{ animationDelay: "0.3s" }} />
    </span>
  );
}
