import { useEffect, useRef, useState } from "react";
import { ArrowDown } from "lucide-react";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import QuickReplies from "./QuickReplies";
import ComparisonMessage from "./ComparisonMessage";
import type { ChatMessage } from "../lib/api";

type Props = {
  messages: ChatMessage[];
  streaming: boolean;
  awaitingFirstToken: boolean;
  onQuickReply: (value: string) => void;
};

const NEAR_BOTTOM_PX = 120;

export default function ChatWindow({ messages, streaming, awaitingFirstToken, onQuickReply }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [nearBottom, setNearBottom] = useState(true);

  const isNearBottom = () => {
    const el = scrollRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
  };

  const scrollToBottom = (smooth = true) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  };

  useEffect(() => {
    if (nearBottom) scrollToBottom();
  }, [messages, streaming, awaitingFirstToken, nearBottom]);

  const lastIndex = messages.length - 1;

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={scrollRef}
        onScroll={() => setNearBottom(isNearBottom())}
        className="h-full overflow-y-auto px-6 py-8"
      >
        <div className="max-w-2xl mx-auto space-y-4">
          {messages.map((m, i) => {
            const isLast = i === lastIndex;
            const prevRole = i > 0 ? messages[i - 1].role : null;
            // Tighter gap for user→assistant Q-A pairs
            const isReply = m.role === "assistant" && prevRole === "user";

            return (
              <div key={i} className={isReply ? "-mt-2" : ""}>
                {m.comparison ? (
                  <ComparisonMessage data={m.comparison} />
                ) : (
                  <MessageBubble role={m.role} content={m.content} />
                )}
                {isLast && m.role === "assistant" && m.quickReplies && !streaming && (
                  <div className="mt-2">
                    <QuickReplies options={m.quickReplies.options} onPick={onQuickReply} />
                  </div>
                )}
              </div>
            );
          })}
          {awaitingFirstToken && <TypingIndicator />}
        </div>
      </div>

      {!nearBottom && (
        <button
          type="button"
          onClick={() => {
            scrollToBottom();
            setNearBottom(true);
          }}
          className="absolute bottom-4 right-4 inline-flex items-center gap-2 px-3 py-2 rounded-full bg-primary text-white text-xs font-medium shadow-md hover:bg-primary-dark focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-colors"
        >
          <ArrowDown size={14} /> new message
        </button>
      )}
    </div>
  );
}
