export default function PDFStatusCard({ sessionId, uploadedPdfs, chunkCount, warning, uploading }) {
  const ready = Boolean(sessionId);

  return (
    <section className="rounded-[32px] border border-white/70 bg-white/88 p-6 shadow-panel backdrop-blur">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky">PDF Status</p>
          <h3 className="font-display text-2xl text-ink">{ready ? "Session active" : "No active session"}</h3>
        </div>
        <span
          className={`rounded-full px-4 py-2 text-sm font-medium ${
            ready ? "bg-moss/10 text-moss" : "bg-sky/10 text-sky"
          }`}
        >
          {uploading ? "Indexing…" : ready ? "Ready" : "Waiting"}
        </span>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="rounded-3xl border border-ink/8 bg-shell p-4">
          <p className="text-sm font-semibold text-ink">Files</p>
          {uploadedPdfs?.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {uploadedPdfs.map((pdf) => (
                <span
                  key={pdf.pdf_id}
                  className="rounded-full border border-sky/10 bg-white px-3 py-1 text-xs font-medium text-slate"
                >
                  {pdf.pdf_name}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate">No PDFs indexed yet.</p>
          )}
        </div>
        <div className="rounded-3xl border border-ink/8 bg-shell p-4">
          <p className="text-sm font-semibold text-ink">Session stats</p>
          <p className="mt-2 text-sm text-slate">
            {uploadedPdfs?.length || 0} PDF(s) · {chunkCount || 0} chunks
          </p>
        </div>
      </div>

      {warning ? (
        <div className="mt-4 rounded-2xl border border-gold/45 bg-gold/10 px-4 py-3 text-sm text-ink">
          {warning}
        </div>
      ) : null}
    </section>
  );
}
