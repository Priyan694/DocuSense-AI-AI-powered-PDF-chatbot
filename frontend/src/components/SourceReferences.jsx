export default function SourceReferences({ sources = [] }) {
  if (!sources.length) {
    return null;
  }

  return (
    <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink/70">
      {sources.map((source) => (
        <span
          key={`${source.chunk_id}-${source.page_number}`}
          className="rounded-full bg-white/80 px-3 py-1 shadow-sm ring-1 ring-ink/10"
        >
          {source.pdf_name} · p.{source.page_number}
          {typeof source.relevance_score === "number" ? ` · score ${source.relevance_score}` : ""}
        </span>
      ))}
    </div>
  );
}

