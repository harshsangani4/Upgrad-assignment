import type { Recommendation } from "../lib/api";
import CourseCard from "./CourseCard";

type Props = { items: Recommendation[] };

export default function CardCarousel({ items }: Props) {
  if (items.length === 0) return null;
  const label = items.length <= 3 ? "Three picks for you" : `${items.length} from the catalog`;
  return (
    <div className="my-3">
      <div className="text-[11px] uppercase tracking-wider text-ink-soft mb-2">
        {label}
      </div>
      <div
        className={
          items.length <= 3
            ? "grid grid-cols-1 md:grid-cols-3 gap-3"
            : "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3"
        }
      >
        {items.map((rec) => (
          <CourseCard key={rec.course_slug} rec={rec} />
        ))}
      </div>
    </div>
  );
}
