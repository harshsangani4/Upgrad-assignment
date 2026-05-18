type Props = {
  onNewChat: () => void;
};

export default function TopBar({ onNewChat }: Props) {
  return (
    <header className="sticky top-0 z-10 h-14 border-b border-border bg-white/80 backdrop-blur flex items-center px-5">
      <div className="flex items-center gap-3">
        <span className="text-2xl font-bold text-primary tracking-tight leading-none">upGrad</span>
        <span className="h-5 w-px bg-border" />
        <span className="text-[13px] text-ink-soft">Course Concierge</span>
      </div>
      <button
        type="button"
        onClick={onNewChat}
        className="ml-auto btn-ghost"
        title="Start a fresh conversation"
      >
        + New chat
      </button>
    </header>
  );
}
