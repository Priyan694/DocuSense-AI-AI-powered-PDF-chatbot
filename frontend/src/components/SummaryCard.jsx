function TermList({ title, items }) {
  return (
    <div className="rounded-3xl border border-ink/8 bg-mist/60 p-4">
      <h4 className="font-display text-sm text-ink">{title}</h4>
      {items?.length ? (
        <div className="mt-3 space-y-3">
          {items.map((item) => (
            <div key={`${title}-${item.term}`} className="rounded-2xl bg-white/80 p-3">
              <p className="text-sm font-semibold text-ink">{item.term}</p>
              <p className="mt-1 text-sm leading-6 text-slate">{item.explanation || "No explanation provided."}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate">No items extracted yet.</p>
      )}
    </div>
  );
}

export default function SummaryCard({ summary, summaryDetails, warning, pdfNames, chunkCount }) {
  return (
    <section className="rounded-[32px] border border-white/70 bg-white/88 p-6 shadow-panel backdrop-blur">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-coral">Auto Summary</p>
          <h2 className="font-display text-2xl text-ink">Learning-focused overview</h2>
        </div>
        <div className="rounded-full border border-sky/10 bg-mist px-4 py-2 text-sm text-slate">
          {chunkCount} chunks indexed
        </div>
      </div>
      <div className="rounded-[28px] bg-gradient-to-br from-sky/10 via-white to-gold/10 p-5">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate">Overall summary</p>
        <p className="mt-3 leading-7 text-ink/85">{summary || "Upload a PDF to generate a summary."}</p>
      </div>

      {summaryDetails ? (
        <div className="mt-5 space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-3xl border border-ink/8 bg-shell p-4">
              <p className="text-sm font-semibold text-ink">Main objective</p>
              <p className="mt-2 text-sm leading-6 text-slate">
                {summaryDetails.main_objective || "Objective not clearly identified yet."}
              </p>
            </div>
            <div className="rounded-3xl border border-ink/8 bg-shell p-4">
              <p className="text-sm font-semibold text-ink">Final takeaway</p>
              <p className="mt-2 text-sm leading-6 text-slate">
                {summaryDetails.final_takeaway || "Takeaway not available yet."}
              </p>
            </div>
          </div>

          <div className="rounded-3xl border border-ink/8 bg-shell p-4">
            <p className="text-sm font-semibold text-ink">Additional explanation</p>
            <p className="mt-2 text-sm leading-6 text-slate">
              {summaryDetails.additional_general_explanation || "No extra explanation was needed."}
            </p>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <TermList title="Important terms" items={summaryDetails.important_terms} />
            <TermList
              title="Useful terms not clearly explained in the PDF"
              items={summaryDetails.missing_but_important_terms}
            />
          </div>
        </div>
      ) : null}

      {pdfNames?.length ? (
        <p className="mt-4 text-sm text-slate">Indexed: {pdfNames.join(", ")}</p>
      ) : null}
      {warning ? (
        <div className="mt-4 rounded-2xl border border-gold/45 bg-gold/10 px-4 py-3 text-sm text-ink">
          {warning}
        </div>
      ) : null}
    </section>
  );
}
