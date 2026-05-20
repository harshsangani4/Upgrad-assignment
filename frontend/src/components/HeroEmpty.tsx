import MessageBubble from "./MessageBubble";

type Props = {
  hookMessage: string;
  starters: string[];
  onStarter: (text: string) => void;
};

export default function HeroEmpty({ hookMessage, starters, onStarter }: Props) {
  return (
    <div className="flex flex-col items-center text-center pt-6 pb-2 fade-in">
      <img
        src="/hero-illustration.svg"
        alt=""
        width={200}
        height={150}
        className="mb-4 select-none"
        draggable={false}
      />
      <div className="w-full text-left">
        <MessageBubble role="assistant" content={hookMessage} />
      </div>
      <div className="flex flex-wrap gap-2 justify-start w-full mt-2 ml-1">
        {starters.map((s, i) => (
          <button
            key={s}
            type="button"
            onClick={() => onStarter(s)}
            className="reply-chip slide-up"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
