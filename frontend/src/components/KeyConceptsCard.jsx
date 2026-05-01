export default function KeyConceptsCard({ keyConcepts = [] }) {
  return (
    <section className="rounded-[32px] border border-white/70 bg-white/88 p-6 shadow-panel backdrop-blur">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss">Key Concepts</p>
      <h3 className="mt-2 font-display text-2xl text-ink">What to focus on</h3>

      {keyConcepts.length ? (
        <div className="mt-5 flex flex-wrap gap-3">
          {keyConcepts.map((concept) => (
            <span
              key={concept}
              className="rounded-full border border-moss/15 bg-moss/8 px-4 py-2 text-sm font-medium text-ink"
            >
              {concept}
            </span>
          ))}
        </div>
      ) : (
        <div className="mt-5 rounded-3xl border border-dashed border-ink/12 bg-shell p-5 text-sm text-slate">
          Upload a PDF to extract the main concepts automatically.
        </div>
      )}
    </section>
  );
}
