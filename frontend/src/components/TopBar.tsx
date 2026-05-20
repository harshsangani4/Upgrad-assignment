type Props = {
  onNewChat: () => void;
};

export default function TopBar({ onNewChat }: Props) {
  return (
    <header className="sticky top-0 z-50 h-14 border-b border-border bg-white flex items-center px-6">
      <div className="flex items-center gap-3">
        <span className="text-2xl font-semibold text-primary tracking-tight leading-none">upGrad</span>
        <span className="h-5 w-px bg-border" />
        <span className="text-sm text-ink-soft">Course Concierge</span>
      </div>
      <button
        type="button"
        onClick={onNewChat}
        className="ml-auto btn-ghost"
        title="Start a fresh conversation"
        aria-label="Start a new chat"
      >
        + New chat
      </button>
    </header>
  );
}
