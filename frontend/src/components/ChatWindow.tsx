import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import CardCarousel from "./CardCarousel";
import QuickReplies from "./QuickReplies";
import type { ChatMessage } from "../lib/api";

type Props = {
  messages: ChatMessage[];
  streaming: boolean;
  onQuickReply: (value: string) => void;
};

export default function ChatWindow({ messages, streaming, onQuickReply }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  const lastIndex = messages.length - 1;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-3xl mx-auto">
        {messages.map((m, i) => {
          const isLast = i === lastIndex;
          return (
            <div key={i}>
              <MessageBubble role={m.role} content={m.content} />
              {m.recommendations && m.recommendations.length > 0 && (
                <CardCarousel items={m.recommendations} />
              )}
              {isLast && m.role === "assistant" && m.quickReplies && !streaming && (
                <QuickReplies
                  options={m.quickReplies.options}
                  onPick={onQuickReply}
                />
              )}
            </div>
          );
        })}
        {streaming && messages[lastIndex]?.role !== "assistant" && (
          <MessageBubble role="assistant" content="" />
        )}
        <div ref={endRef} className="h-2" />
      </div>
    </div>
  );
}
