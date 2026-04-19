interface BreedingReportProps {
  report?: string;
  lessons?: string[];
}

export default function BreedingReport({ report, lessons }: BreedingReportProps) {
  if (!report && (!lessons || lessons.length === 0)) {
    return null;
  }
  return (
    <div className="rounded-xl bg-surface-container-low p-5">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        Breeder's Reasoning
      </p>
      {report && (
        <blockquote className="mt-3 border-l-2 border-primary/40 pl-4 text-sm italic text-on-surface">
          {report}
        </blockquote>
      )}
      {lessons && lessons.length > 0 && (
        <div className="mt-4">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            New Lessons This Generation
          </p>
          <ul className="mt-2 space-y-2">
            {lessons.map((lesson, i) => (
              <li key={i} className="flex gap-2 text-sm text-on-surface">
                <span className="text-secondary">•</span>
                <span>{lesson}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
