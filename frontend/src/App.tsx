import { useEffect, useRef, useState } from "react";
import TopBar from "./components/TopBar";
import ChatWindow from "./components/ChatWindow";
import Composer from "./components/Composer";
import { streamChat, type ChatMessage } from "./lib/api";

const SESSION_KEY = "upgrad-concierge-session-id";

const HOOK_MESSAGE =
  "Hey, I'm here to help you figure out which upGrad course is actually right for you, not just the shiny one. Think of me as the friend who's done the homework. So, what's pulling you here? A specific goal, or just browsing?";

const STARTER_CHIPS = [
  "AI / ML",
  "Data Science",
  "Product Mgmt",
  "Generative AI",
  "MBA / DBA",
  "Software Engg",
  "Show me everything",
];

function initialMessages(): ChatMessage[] {
  return [
    {
      role: "assistant",
      content: HOOK_MESSAGE,
      quickReplies: { slot: "domain_interest", options: STARTER_CHIPS },
    },
  ];
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(
    () => localStorage.getItem(SESSION_KEY)
  );
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (sessionId) localStorage.setItem(SESSION_KEY, sessionId);
    else localStorage.removeItem(SESSION_KEY);
  }, [sessionId]);

  const handleNewChat = () => {
    abortRef.current?.abort();
    setSessionId(null);
    setMessages(initialMessages());
    setStreaming(false);
  };

  const send = async (text: string) => {
    setMessages((m) => {
      // clear quick replies from the previous assistant message — they're consumed
      const cleared = m.map((msg, i) =>
        i === m.length - 1 && msg.role === "assistant"
          ? { ...msg, quickReplies: undefined }
          : msg
      );
      return [...cleared, { role: "user", content: text }];
    });
    setStreaming(true);

    let assistantStarted = false;
    let pendingQuickReplies: ChatMessage["quickReplies"];
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const startAssistantIfNeeded = (initialContent: string) => {
      setMessages((m) => {
        if (assistantStarted) return m;
        assistantStarted = true;
        return [
          ...m,
          {
            role: "assistant",
            content: initialContent,
            quickReplies: pendingQuickReplies,
          },
        ];
      });
    };

    try {
      await streamChat(
        sessionId,
        text,
        (evt) => {
          if (evt.type === "session") {
            setSessionId(evt.sessionId);
          } else if (evt.type === "quick_replies") {
            pendingQuickReplies = evt.payload;
          } else if (evt.type === "token") {
            if (!assistantStarted) {
              startAssistantIfNeeded(evt.value);
              return;
            }
            setMessages((m) => {
              const last = m[m.length - 1];
              if (last?.role !== "assistant") {
                return [
                  ...m,
                  { role: "assistant", content: evt.value, quickReplies: pendingQuickReplies },
                ];
              }
              return [
                ...m.slice(0, -1),
                { ...last, content: last.content + evt.value },
              ];
            });
          } else if (evt.type === "recommendations") {
            setMessages((m) => {
              const last = m[m.length - 1];
              if (last?.role === "assistant") {
                return [
                  ...m.slice(0, -1),
                  { ...last, recommendations: evt.items },
                ];
              }
              return [
                ...m,
                { role: "assistant", content: "", recommendations: evt.items },
              ];
            });
          } else if (evt.type === "error") {
            setMessages((m) => [
              ...m,
              { role: "assistant", content: `(error: ${evt.message})` },
            ]);
          }
        },
        ctrl.signal
      );
    } catch (err: any) {
      if (err?.name !== "AbortError") {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: "(connection error — is the backend running on :8000?)",
          },
        ]);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  return (
    <div className="flex flex-col h-full bg-white">
      <TopBar onNewChat={handleNewChat} />
      <ChatWindow messages={messages} streaming={streaming} onQuickReply={send} />
      <Composer onSend={send} disabled={streaming} />
    </div>
  );
}
