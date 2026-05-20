type Props = {
  role: "user" | "assistant";
  content: string;
};

export default function MessageBubble({ role, content }: Props) {
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
