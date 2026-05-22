import { useState } from "react";
import { submitLead, dismissLead } from "../lib/api";

type Props = {
  formId: string;
  sessionId: string;
  courseSlug: string | null;
  courseTitle: string | null;
  onSubmitted: (confirmText: string) => void;
  onDismissed: (reply: string) => void;
};

const PHONE_OK = /^(\+?\d{1,3}[- ]?)?\d{10}$/;
const EMAIL_OK = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LeadFormMessage({
  formId,
  sessionId,
  courseSlug,
  courseTitle,
  onSubmitted,
  onDismissed,
}: Props) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const phoneOk = PHONE_OK.test(phone.replace(/\s|-/g, ""));
  const emailOk = EMAIL_OK.test(email);
  const canSubmit = !!name.trim() && emailOk && phoneOk && consent && !submitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitLead({
        session_id: sessionId,
        form_id: formId,
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim(),
        course_slug: courseSlug,
        consent,
      });
      onSubmitted(res.message || "Got it. The team will reach out within one business day.");
    } catch (err: any) {
      setError(err?.message ?? "Couldn't submit. Try once more?");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDismiss = async () => {
    const res = await dismissLead(sessionId, formId).catch(() => ({}));
    onDismissed(res.message || "All good, no pressure. What else do you want to dig into?");
  };

  const inputClass =
    "mt-1 w-full rounded-md border border-border-strong bg-white px-3 py-2 text-ink " +
    "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2";

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="Connect with the upGrad team"
      className="bg-surface-alt border border-border-strong rounded-2xl p-6 my-2 max-w-md space-y-3 slide-up"
    >
      <div className="text-sm text-ink-muted">
        {courseTitle ? (
          <>
            Quick details so the team can reach out about{" "}
            <span className="text-ink font-medium">{courseTitle}</span>.
          </>
        ) : (
          <>Quick details so the team can reach out.</>
        )}
      </div>

      <label className="block">
        <span className="text-xs text-ink-muted">Name</span>
        <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required />
      </label>

      <label className="block">
        <span className="text-xs text-ink-muted">Email</span>
        <input type="email" className={inputClass} value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
      </label>

      <label className="block">
        <span className="text-xs text-ink-muted">Phone</span>
        <input
          type="tel"
          inputMode="tel"
          placeholder="+91 98xxxxxxxx"
          className={inputClass}
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          autoComplete="tel"
          required
        />
      </label>

      <label className="flex items-start gap-2 text-xs text-ink-muted">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-0.5 accent-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
          required
        />
        <span>OK to share these details with the upGrad team so they can call or email me about this program.</span>
      </label>

      {error && (
        <div className="text-sm text-warning" role="alert">
          {error}
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button type="submit" disabled={!canSubmit} className="btn-primary flex-1">
          {submitting ? "Sending..." : "Connect me"}
        </button>
        <button
          type="button"
          onClick={handleDismiss}
          className="btn-ghost border border-border-strong"
        >
          Not now
        </button>
      </div>
    </form>
  );
}
