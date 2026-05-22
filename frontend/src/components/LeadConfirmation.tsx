import { CheckCircle2 } from "lucide-react";

type Props = { text: string };

export default function LeadConfirmation({ text }: Props) {
  return (
    <div className="flex items-start gap-2 bg-pill border border-primary/30 rounded-2xl p-4 my-2 max-w-md slide-up">
      <CheckCircle2 size={18} className="text-success shrink-0 mt-0.5" />
      <p className="text-sm text-ink leading-relaxed">{text}</p>
    </div>
  );
}
