export type Faculty = { name: string; title?: string };

export type Recommendation = {
  course_slug: string;
  course_url: string;
  title: string;
  provider: string | null;
  duration_label: string | null;
  fee_bucket: string | null;
  why_this_fits: string;
  faculty?: Faculty[];
};

export type QuickReplyPayload = {
  slot: string;
  options: string[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  recommendations?: Recommendation[];
  quickReplies?: QuickReplyPayload;
};

export type StreamEvent =
  | { type: "session"; sessionId: string }
  | { type: "token"; value: string }
  | { type: "recommendations"; items: Recommendation[] }
  | { type: "quick_replies"; payload: QuickReplyPayload }
  | { type: "error"; message: string }
  | { type: "done" };

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

function parseEventBlock(block: string): StreamEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const raw of block.split("\n")) {
    const line = raw.trimEnd();
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  const dataStr = dataLines.join("\n");
  let payload: any = {};
  try {
    payload = JSON.parse(dataStr);
  } catch {
    payload = { value: dataStr };
  }
  switch (event) {
    case "session":
      return { type: "session", sessionId: payload.session_id };
    case "token":
      return { type: "token", value: payload.value ?? "" };
    case "recommendations":
      return { type: "recommendations", items: payload.items ?? [] };
    case "quick_replies":
      return {
        type: "quick_replies",
        payload: { slot: payload.slot, options: payload.options ?? [] },
      };
    case "error":
      return { type: "error", message: payload.message ?? "unknown error" };
    case "done":
      return { type: "done" };
    default:
      return null;
  }
}

export async function streamChat(
  sessionId: string | null,
  message: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`chat request failed: ${resp.status}`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const evt = parseEventBlock(block);
      if (evt) onEvent(evt);
    }
  }
  if (buffer.trim()) {
    const evt = parseEventBlock(buffer);
    if (evt) onEvent(evt);
  }
}

export async function fetchHook(): Promise<string> {
  try {
    const resp = await fetch(`${API_BASE}/api/hook`);
    if (!resp.ok) throw new Error("hook fetch failed");
    const data = await resp.json();
    return data.message as string;
  } catch {
    return "Hey — I'm here to help you figure out which upGrad course is actually right for you, not just which one looks shiny. Think of me less as a brochure and more as the friend who's done this homework already. So — what's pulling you here? A specific goal, or just window-shopping for now?";
  }
}
