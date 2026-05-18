import type { Recommendation } from "../lib/api";

type Props = { rec: Recommendation };

export default function CourseCard({ rec }: Props) {
  const chips = [rec.duration_label, rec.fee_bucket].filter(Boolean) as string[];
  const facultyNames = (rec.faculty ?? []).map((f) => f.name).slice(0, 3);

  return (
    <a
      href={rec.course_url}
      target="_blank"
      rel="noreferrer noopener"
      className="group flex flex-col rounded-xl border border-border bg-white p-4 hover:border-primary hover:shadow-card transition-all h-full slide-up"
    >
      <div className="text-[11px] uppercase tracking-wider text-ink-soft mb-1.5 truncate">
        {rec.provider || "upGrad"}
      </div>
      <h3 className="text-[15px] font-semibold text-ink leading-snug mb-2.5 line-clamp-3 group-hover:text-primary-dark transition-colors">
        {rec.title}
      </h3>
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2.5">
          {chips.map((c) => (
            <span key={c} className="chip">
              {c}
            </span>
          ))}
        </div>
      )}
      <p className="text-[13px] text-ink-soft leading-relaxed flex-1 mb-3 line-clamp-4">
        {rec.why_this_fits}
      </p>
      {facultyNames.length > 0 && (
        <div className="text-[12px] text-ink-soft mb-3 leading-snug">
          <span className="font-medium text-ink">Faculty:</span>{" "}
          {facultyNames.join(", ")}
          {(rec.faculty?.length ?? 0) > facultyNames.length && " +"}
        </div>
      )}
      <div className="text-[13px] font-medium text-primary group-hover:text-primary-dark mt-auto">
        View course →
      </div>
    </a>
  );
}
