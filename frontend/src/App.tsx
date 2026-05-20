import { useEffect, useRef, useState } from "react";
import TopBar from "./components/TopBar";
import Progress from "./components/Progress";
import ChatWindow from "./components/ChatWindow";
import HeroEmpty from "./components/HeroEmpty";
import Composer from "./components/Composer";
import PicksRail from "./components/PicksRail";
import {
  streamChat,
  fetchMore,
  type ChatMessage,
  type Recommendation,
  type Progress as ProgressType,
} from "./lib/api";

const SESSION_KEY = "upgrad-concierge-session-id";

const HOOK_MESSAGE =
  "Hey, I'm here to help you figure out which upGrad course is actually right for you, not just the shiny one. Think of me as the friend who's done the homework. So, what's pulling you here? A specific goal, or just browsing?";

const STARTERS = ["I want to switch into AI", "I'm exploring an MBA", "Help me upskill in data"];

function initialMessages(): ChatMessage[] {
  return [{ role: "assistant", content: HOOK_MESSAGE }];
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(() => localStorage.getItem(SESSION_KEY));
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [progress, setProgress] = useState<ProgressType>({ filled: 0, total: 0 });
  const [streaming, setStreaming] = useState(false);
  const [awaitingFirstToken, setAwaitingFirstToken] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [exhausted, setExhausted] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (sessionId) localStorage.setItem(SESSION_KEY, sessionId);
    else localStorage.removeItem(SESSION_KEY);
  }, [sessionId]);

  const showHero = messages.length === 1 && messages[0].role === "assistant" && recommendations.length === 0;

  const handleNewChat = () => {
    abortRef.current?.abort();
    setSessionId(null);
    setMessages(initialMessages());
    setRecommendations([]);
    setProgress({ filled: 0, total: 0 });
    setExhausted(false);
    setStreaming(false);
    setAwaitingFirstToken(false);
  };

  const send = async (text: string) => {
    setMessages((m) => {
      const cleared = m.map((msg, i) =>
        i === m.length - 1 && msg.role === "assistant" ? { ...msg, quickReplies: undefined } : msg
      );
      return [...cleared, { role: "user", content: text }];
    });
    setStreaming(true);
    setAwaitingFirstToken(true);

    let assistantStarted = false;
    let pendingQuickReplies: ChatMessage["quickReplies"];
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      await streamChat(
        sessionId,
        text,
        (evt) => {
          if (evt.type === "session") {
            setSessionId(evt.sessionId);
          } else if (evt.type === "progress") {
            setProgress(evt.progress);
          } else if (evt.type === "quick_replies") {
            pendingQuickReplies = evt.payload;
          } else if (evt.type === "token") {
            setAwaitingFirstToken(false);
            setMessages((m) => {
              if (!assistantStarted) {
                assistantStarted = true;
                return [...m, { role: "assistant", content: evt.value, quickReplies: pendingQuickReplies }];
              }
              const last = m[m.length - 1];
              if (last?.role !== "assistant") {
                return [...m, { role: "assistant", content: evt.value, quickReplies: pendingQuickReplies }];
              }
              return [...m.slice(0, -1), { ...last, content: last.content + evt.value }];
            });
          } else if (evt.type === "recommendations") {
            setExhausted(false);
            if (evt.mode === "append") {
              setRecommendations((prev) => {
                const seen = new Set(prev.map((r) => r.course_slug));
                return [...prev, ...evt.items.filter((r) => !seen.has(r.course_slug))];
              });
            } else {
              setRecommendations(evt.items);
            }
          } else if (evt.type === "error") {
            setMessages((m) => [...m, { role: "assistant", content: `(error: ${evt.message})` }]);
          }
        },
        ctrl.signal
      );
    } catch (err: any) {
      if (err?.name !== "AbortError") {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: "(connection error, is the backend running?)" },
        ]);
      }
    } finally {
      setStreaming(false);
      setAwaitingFirstToken(false);
      abortRef.current = null;
    }
  };

  const handleSeeMore = async () => {
    if (!sessionId || loadingMore) return;
    setLoadingMore(true);
    try {
      const more = await fetchMore(sessionId, recommendations.length, 3);
      if (more.length === 0) {
        setExhausted(true);
      } else {
        setRecommendations((prev) => {
          const seen = new Set(prev.map((r) => r.course_slug));
          const fresh = more.filter((r) => !seen.has(r.course_slug));
          if (fresh.length < 3) setExhausted(true);
          return [...prev, ...fresh];
        });
      }
    } catch {
      setExhausted(true);
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div className="h-[100dvh] flex flex-col overflow-hidden">
      <TopBar onNewChat={handleNewChat} />
      <Progress filled={progress.filled} total={progress.total} />

      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden w-full max-w-[1280px] mx-auto">
        <section className="flex flex-col flex-1 min-w-0 lg:border-r border-border overflow-hidden">
          {showHero ? (
            <div className="flex-1 overflow-y-auto px-4 py-2">
              <div className="max-w-2xl mx-auto">
                <HeroEmpty hookMessage={HOOK_MESSAGE} starters={STARTERS} onStarter={send} />
              </div>
            </div>
          ) : (
            <ChatWindow
              messages={messages}
              streaming={streaming}
              awaitingFirstToken={awaitingFirstToken}
              onQuickReply={send}
            />
          )}
          <Composer onSend={send} disabled={streaming} />
        </section>

        <section
          className={
            "lg:w-[380px] shrink-0 overflow-hidden bg-white/40 " +
            (recommendations.length === 0
              ? "hidden lg:flex lg:flex-col"
              : "flex flex-col max-lg:max-h-[45vh] max-lg:border-t border-border")
          }
        >
          <PicksRail
            items={recommendations}
            onSeeMore={handleSeeMore}
            loadingMore={loadingMore}
            exhausted={exhausted}
          />
        </section>
      </div>
    </div>
  );
}
