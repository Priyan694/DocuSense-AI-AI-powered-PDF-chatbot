export default function SummaryCard({ summary, warning, pdfNames, chunkCount }) {
  return (
    <section className="rounded-[28px] bg-white/90 p-6 shadow-panel backdrop-blur">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-coral">Auto Summary</p>
          <h2 className="font-display text-2xl text-ink">What the PDF is about</h2>
        </div>
        <div className="rounded-full bg-mist px-4 py-2 text-sm text-ink/70">{chunkCount} chunks indexed</div>
      </div>
      <p className="leading-7 text-ink/80">{summary || "Upload a PDF to generate a summary."}</p>
      {pdfNames?.length ? (
        <p className="mt-4 text-sm text-ink/60">Indexed: {pdfNames.join(", ")}</p>
      ) : null}
      {warning ? (
        <div className="mt-4 rounded-2xl border border-gold/50 bg-gold/10 px-4 py-3 text-sm text-ink">
          {warning}
        </div>
      ) : null}
    </section>
  );
}

