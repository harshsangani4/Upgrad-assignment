import { ArrowRight } from "lucide-react";
import type { Recommendation } from "../lib/api";

type ComparisonCourse = {
  slug: string;
  title: string;
  provider: string | null;
  logo_url: string | null;
  duration_label: string | null;
  format: string | null;
  level: string | null;
  fee_bucket: string | null;
  emi_starts_from_inr: number | null;
  min_years_exp: number | null;
  min_degree: string | null;
  top_tools: string[];
  target_roles_top: string[];
};

export type ComparisonData = {
  comparison_id: string;
  courses: ComparisonCourse[];
  summary: string;
};

type Props = {
  data: ComparisonData;
};

function initials(provider: string | null): string {
  if (!provider) return "uG";
  const words = provider.replace(/[^a-zA-Z ]/g, "").trim().split(/\s+/);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

const ROWS: { label: string; key: keyof ComparisonCourse }[] = [
  { label: "Duration", key: "duration_label" },
  { label: "Format", key: "format" },
  { label: "Level", key: "level" },
  { label: "Fee bucket", key: "fee_bucket" },
  { label: "EMI from", key: "emi_starts_from_inr" },
  { label: "Min exp", key: "min_years_exp" },
  { label: "Min degree", key: "min_degree" },
  { label: "Top tools", key: "top_tools" },
];

function fmt(val: ComparisonCourse[keyof ComparisonCourse]): string {
  if (val === null || val === undefined) return "—";
  if (Array.isArray(val)) return val.length > 0 ? val.join(", ") : "—";
  if (typeof val === "number") {
    // emi_starts_from_inr or min_years_exp
    return val > 1000 ? `₹${val.toLocaleString("en-IN")}` : `${val} yr${val !== 1 ? "s" : ""}`;
  }
  return String(val);
}

// Pick letter label A / B / C
const LABELS = ["A", "B", "C"];

export default function ComparisonMessage({ data }: Props) {
  const { courses, summary } = data;
  if (!courses.length) return null;

  const courseUrls = courses.map((c) => {
    // Find URL from course slug — we'll rely on the card context not stored here;
    // use upGrad search URL as fallback
    return `https://www.upgrad.com/`;
  });

  return (
    <div className="w-full rounded-2xl border border-border bg-surface shadow-sm overflow-hidden my-2 fade-in">
      {/* Header */}
      <div className="px-5 py-3 border-b border-border flex items-center gap-2">
        <span className="text-[13px] font-semibold text-ink">
          Comparing {courses.length} course{courses.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Scrollable table */}
      <div className="overflow-x-auto">
        <table className="w-full text-[12px] border-collapse min-w-[480px]">
          <thead>
            <tr className="border-b border-border">
              {/* Sticky first column placeholder */}
              <th className="sticky left-0 z-10 bg-surface px-4 py-3 w-[110px] text-left text-[11px] font-medium text-ink-soft" />
              {courses.map((c, i) => (
                <th
                  key={c.slug}
                  className="px-4 py-3 text-left align-top"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-7 h-7 rounded-full bg-primary/10 text-primary text-[10px] font-bold flex items-center justify-center shrink-0">
                      {LABELS[i]}
                    </div>
                    {c.logo_url ? (
                      <img src={c.logo_url} alt="" className="w-5 h-5 object-contain" />
                    ) : (
                      <span className="text-[9px] font-semibold text-ink-soft">
                        {initials(c.provider)}
                      </span>
                    )}
                  </div>
                  <div className="font-semibold text-ink leading-snug line-clamp-2">
                    {c.title}
                  </div>
                  <div className="text-ink-soft text-[11px] mt-0.5">{c.provider || "upGrad"}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label} className="border-b border-border last:border-0 hover:bg-white/50 transition-colors">
                <td className="sticky left-0 z-10 bg-surface px-4 py-2.5 text-ink-soft font-medium whitespace-nowrap">
                  {row.label}
                </td>
                {courses.map((c) => (
                  <td key={c.slug} className="px-4 py-2.5 text-ink">
                    {fmt(c[row.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      {summary && (
        <div className="px-5 py-4 border-t border-border text-[13px] text-ink leading-relaxed">
          {summary}
        </div>
      )}

      {/* Action buttons */}
      <div className="px-5 py-3 border-t border-border flex flex-wrap gap-2">
        {courses.map((c, i) => (
          <a
            key={c.slug}
            href={`https://www.upgrad.com/`}
            target="_blank"
            rel="noreferrer noopener"
            className="btn-ghost border border-border text-[12px] px-3 py-1.5 rounded-lg"
          >
            Open {LABELS[i]} <ArrowRight size={12} className="inline ml-0.5" />
          </a>
        ))}
      </div>
    </div>
  );
}
