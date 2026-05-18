type Props = {
  options: string[];
  onPick: (value: string) => void;
  disabled?: boolean;
};

export default function QuickReplies({ options, onPick, disabled }: Props) {
  if (!options || options.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-2 mb-2 ml-1 max-w-[78%] slide-up">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onPick(opt)}
          disabled={disabled}
          className="reply-chip"
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
