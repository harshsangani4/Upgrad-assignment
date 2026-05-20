export default function TypingIndicator() {
  return (
    <div className="flex justify-start my-2 fade-in">
      <div className="rounded-2xl rounded-bl-md bg-surface px-4 py-3">
        <span className="inline-flex items-center">
          <span className="typing-dot" style={{ animationDelay: "0s" }} />
          <span className="typing-dot" style={{ animationDelay: "0.15s" }} />
          <span className="typing-dot" style={{ animationDelay: "0.3s" }} />
        </span>
      </div>
    </div>
  );
}
