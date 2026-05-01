const providers = [
  { value: "minimax", label: "MiniMax" },
  { value: "groq", label: "Groq Llama" },
];

export default function UploadPDF({
  files,
  setFiles,
  llmProvider,
  setLlmProvider,
  onUpload,
  loading,
  onReset,
  hasSession,
}) {
  return (
    <section className="rounded-[28px] bg-ink p-6 text-white shadow-panel">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-gold">PDF RAG Workspace</p>
      <h1 className="mt-2 font-display text-4xl leading-tight">Upload, summarize, and chat with your PDFs.</h1>
      <p className="mt-4 max-w-xl text-sm leading-6 text-white/75">
        The assistant stays grounded in the uploaded files, shows page references, and warns when the answer is not in the PDF.
      </p>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <label className="rounded-3xl border border-white/15 bg-white/10 p-4">
          <span className="mb-3 block text-sm font-medium">Choose PDF files</span>
          <input
            type="file"
            accept=".pdf,application/pdf"
            multiple
            onChange={(event) => setFiles(Array.from(event.target.files || []))}
            className="block w-full text-sm text-white file:mr-4 file:rounded-full file:border-0 file:bg-gold file:px-4 file:py-2 file:font-semibold file:text-ink"
          />
        </label>

        <label className="rounded-3xl border border-white/15 bg-white/10 p-4">
          <span className="mb-3 block text-sm font-medium">LLM provider</span>
          <select
            value={llmProvider}
            onChange={(event) => setLlmProvider(event.target.value)}
            className="w-full rounded-2xl border border-white/10 bg-ink/70 px-4 py-3 text-white outline-none"
          >
            {providers.map((provider) => (
              <option key={provider.value} value={provider.value}>
                {provider.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <button
          onClick={onUpload}
          disabled={!files.length || loading}
          className="rounded-full bg-coral px-5 py-3 text-sm font-semibold text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Indexing PDFs..." : "Upload and Index"}
        </button>
        <button
          onClick={onReset}
          disabled={!hasSession}
          className="rounded-full border border-white/20 px-5 py-3 text-sm font-semibold text-white/90 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Clear PDF Session
        </button>
      </div>
    </section>
  );
}

