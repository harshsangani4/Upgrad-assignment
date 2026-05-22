import { useEffect, useRef, useState } from "react";
import TopBar from "./components/TopBar";
import Progress from "./components/Progress";
import ChatWindow from "./components/ChatWindow";
import HeroEmpty from "./components/HeroEmpty";
import Composer from "./components/Composer";
import PicksRail from "./components/PicksRail";
import {
  streamChat,
  streamCourseAsk,
  fetchMore,
  fetchComparison,
  type ChatMessage,
  type Recommendation,
  type Progress as ProgressType,
  type ComparisonResult,
  type AttachedCourse,
} from "./lib/api";

const SESSION_KEY = "upgrad-concierge-session-id";
const COURSE_MSG_AUTO_CLEAR = 3;

const HOOK_MESSAGE =
  "Hey, I'm here to help you figure out which upGrad course is actually right for you, not just the shiny one. Think of me as the friend who's done the homework. So, what's pulling you here? A specific goal, or just browsing?";

const STARTERS = [
  "I want to switch into AI",
  "I'm exploring an MBA",
  "Help me upskill in data",
  "Aiming for a promotion",
  "Just browsing for now",
];

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

  // Task 9.4 — attached course
  const [attachedCourse, setAttachedCourse] = useState<AttachedCourse | null>(null);
  const [courseMessageCount, setCourseMessageCount] = useState(0);

  // Task 9.5 — compare selection
  const [selectedSlugs, setSelectedSlugs] = useState<string[]>([]);
  const [comparingLoading, setComparingLoading] = useState(false);

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
    setAttachedCourse(null);
    setCourseMessageCount(0);
    setSelectedSlugs([]);
  };

  // ---- Core streaming helper ------------------------------------------------

  const _runStream = async (
    streamFn: (onEvent: Parameters<typeof streamChat>[2], signal: AbortSignal) => Promise<void>
  ) => {
    setStreaming(true);
    setAwaitingFirstToken(true);

    let assistantStarted = false;
    let pendingQuickReplies: ChatMessage["quickReplies"];
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      await streamFn((evt) => {
        if (evt.type === "session") {
          setSessionId(evt.sessionId);
        } else if (evt.type === "progress") {
          setProgress(evt.progress);
        } else if (evt.type === "quick_replies") {
          pendingQuickReplies = evt.payload;
        } else if (evt.type === "focused_course") {
          // Backend recognized a course by name; keep the thread on it so follow-ups
          // route to course Q&A and the chip shows above the composer.
          setAttachedCourse(evt.course);
          setCourseMessageCount(0);
        } else if (evt.type === "lead_form") {
          // Render the inline lead-capture form as its own message below the opener.
          setMessages((m) => [...m, { role: "assistant", content: "", leadForm: evt.payload }]);
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
          const now = Date.now();
          setExhausted(false);
          if (evt.mode === "append") {
            setRecommendations((prev) => {
              const seen = new Set(prev.map((r) => r.course_slug));
              return [...prev, ...evt.items.filter((r) => !seen.has(r.course_slug)).map((r) => ({ ...r, addedAt: now }))];
            });
          } else {
            setRecommendations(evt.items.map((r) => ({ ...r, addedAt: now })));
          }
        } else if (evt.type === "error") {
          const friendly = evt.message && !/error code|rate.?limit|\b429\b|traceback|exception/i.test(evt.message)
            ? evt.message
            : "I'm getting a lot of requests right now. Give me a few seconds and try that again.";
          setMessages((m) => [...m, { role: "assistant", content: friendly }]);
        }
      }, ctrl.signal);
    } catch (err: any) {
      if (err?.name !== "AbortError") {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: "I couldn't reach the server just now. Please try again in a moment." },
        ]);
      }
    } finally {
      setStreaming(false);
      setAwaitingFirstToken(false);
      abortRef.current = null;
    }
  };

  // ---- Send: normal chat or course Q&A ------------------------------------

  const send = async (text: string, attached?: AttachedCourse) => {
    // Clear quick replies on last assistant message; attach the course to the user
    // message so it shows as a reference (caption + chip) in the bubble.
    setMessages((m) =>
      m.map((msg, i) =>
        i === m.length - 1 && msg.role === "assistant" ? { ...msg, quickReplies: undefined } : msg
      ).concat([{ role: "user", content: text, attachedCourse: attached ?? undefined }])
    );

    if (attached) {
      // Course Q&A path
      const newCount = courseMessageCount + 1;
      setCourseMessageCount(newCount);
      if (newCount >= COURSE_MSG_AUTO_CLEAR) {
        setAttachedCourse(null);
        setCourseMessageCount(0);
      }

      await _runStream((onEvent, signal) =>
        streamCourseAsk(attached.slug, sessionId, text, onEvent, signal)
      );
    } else {
      // Normal chat path
      await _runStream((onEvent, signal) =>
        streamChat(sessionId, text, onEvent, signal)
      );
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
        const now = Date.now();
        setRecommendations((prev) => {
          const seen = new Set(prev.map((r) => r.course_slug));
          const fresh = more.filter((r) => !seen.has(r.course_slug)).map((r) => ({ ...r, addedAt: now }));
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

  // ---- Task 9.4 — ask about course ----------------------------------------

  const handleAskAbout = (course: AttachedCourse) => {
    setAttachedCourse(course);
    setCourseMessageCount(0);
  };

  const handleDismissCourse = () => {
    setAttachedCourse(null);
    setCourseMessageCount(0);
  };

  const handleDropCourse = (course: AttachedCourse) => {
    setAttachedCourse(course);
    setCourseMessageCount(0);
  };

  // ---- Task 9.5 — compare -------------------------------------------------

  const handleToggleCompare = (slug: string) => {
    setSelectedSlugs((prev) => {
      if (prev.includes(slug)) return prev.filter((s) => s !== slug);
      if (prev.length >= 3) return prev; // max 3
      return [...prev, slug];
    });
  };

  const handleClearCompare = () => setSelectedSlugs([]);

  // ---- Phase 13 — lead capture --------------------------------------------

  const handleLeadSubmitted = (index: number, confirmText: string) => {
    setMessages((m) =>
      m.map((msg, i) => (i === index ? { role: "assistant", content: "", leadConfirm: confirmText } : msg))
    );
    setAttachedCourse(null);
  };

  const handleLeadDismissed = (index: number, reply: string) => {
    setMessages((m) =>
      m.map((msg, i) => (i === index ? { role: "assistant", content: reply } : msg))
    );
  };

  const handleCompare = async () => {
    if (!sessionId || selectedSlugs.length < 2 || comparingLoading) return;
    setComparingLoading(true);
    try {
      const result: ComparisonResult = await fetchComparison(sessionId, selectedSlugs);
      // Inject comparison as a special assistant message
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "", comparison: result },
      ]);
      setSelectedSlugs([]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "(comparison failed — please try again)" },
      ]);
    } finally {
      setComparingLoading(false);
    }
  };

  return (
    <div className="h-[100dvh] flex flex-col overflow-hidden">
      <TopBar onNewChat={handleNewChat} />
      <Progress filled={progress.filled} total={progress.total} />

      <div className="flex-1 flex flex-col lg:grid lg:grid-cols-[1fr_420px] lg:gap-8 overflow-hidden w-full max-w-[1280px] mx-auto">
        <section className="flex flex-col flex-1 min-w-0 lg:border-r border-border overflow-hidden">
          {showHero ? (
            <div className="flex-1 overflow-y-auto px-6 py-8">
              <div className="max-w-2xl mx-auto">
                <HeroEmpty hookMessage={HOOK_MESSAGE} starters={STARTERS} onStarter={(t) => send(t)} />
              </div>
            </div>
          ) : (
            <ChatWindow
              messages={messages}
              streaming={streaming}
              sessionId={sessionId}
              onLeadSubmitted={handleLeadSubmitted}
              onLeadDismissed={handleLeadDismissed}
              awaitingFirstToken={awaitingFirstToken}
              onQuickReply={(t) => send(t)}
            />
          )}
          <Composer
            onSend={send}
            disabled={streaming}
            attachedCourse={attachedCourse}
            courseMessageCount={courseMessageCount}
            onDismissCourse={handleDismissCourse}
            onDropCourse={handleDropCourse}
          />
        </section>

        <section
          className={
            "lg:shrink-0 overflow-hidden bg-white/40 " +
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
            selectedSlugs={selectedSlugs}
            onToggleCompare={handleToggleCompare}
            onCompare={handleCompare}
            onClearCompare={handleClearCompare}
            comparingLoading={comparingLoading}
            onAskAbout={handleAskAbout}
          />
        </section>
      </div>
    </div>
  );
}
