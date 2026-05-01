import { useState } from "react";
import SourceReferences from "./SourceReferences";

const actionButtons = [
  { key: "simple_explain", label: "Explain Simply" },
  { key: "key_points", label: "Key Points" },
  { key: "mcqs", label: "Generate 10 MCQs" },
  { key: "flashcards", label: "Flashcards" },
  { key: "rewrite", label: "Rewrite PDF" },
  { key: "compare", label: "Compare Content" },
];

export default function ChatBox({
  messages,
  onAsk,
  onAction,
  asking,
  hasSession,
  llmProvider,
}) {
  const [question, setQuestion] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }
    await onAsk(question);
    setQuestion("");
  };

  return (
    <section className="flex h-[780px] flex-col rounded-[28px] bg-white/90 p-6 shadow-panel backdrop-blur">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss">Chat</p>
          <h2 className="font-display text-2xl text-ink">Ask questions from the uploaded PDF</h2>
        </div>
        <div className="rounded-full bg-mist px-4 py-2 text-sm text-ink/70">Model: {llmProvider}</div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {actionButtons.map((action) => (
          <button
            key={action.key}
            onClick={() => onAction(action.key)}
            disabled={!hasSession || asking}
            className="rounded-full border border-ink/10 bg-mist px-4 py-2 text-sm font-medium text-ink transition hover:bg-gold/30 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {action.label}
          </button>
        ))}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto pr-2">
        {messages.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-ink/15 bg-mist/70 p-6 text-sm text-ink/60">
            Upload a PDF, then ask a question or use one of the quick actions.
          </div>
        ) : null}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`max-w-[90%] rounded-[24px] px-5 py-4 ${
              message.role === "user"
                ? "ml-auto bg-coral text-white"
                : "bg-mist text-ink"
            }`}
          >
            <p className="whitespace-pre-wrap leading-7">{message.content}</p>
            {message.confidence != null && message.role === "assistant" ? (
              <p className="mt-3 text-xs text-ink/60">
                Confidence: {message.confidence} {message.weakContext ? "· retrieved context is weak" : ""}
              </p>
            ) : null}
            {message.rewrittenQuestion ? (
              <p className="mt-2 text-xs text-ink/60">Rewritten query: {message.rewrittenQuestion}</p>
            ) : null}
            <SourceReferences sources={message.sources} />
          </div>
        ))}

        {asking ? (
          <div className="max-w-[90%] rounded-[24px] bg-mist px-5 py-4 text-ink">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-coral" />
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-gold [animation-delay:160ms]" />
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-moss [animation-delay:320ms]" />
            </div>
          </div>
        ) : null}
      </div>

      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about the uploaded PDF..."
          disabled={!hasSession || asking}
          className="h-28 w-full resize-none rounded-[24px] border border-ink/10 bg-mist/70 px-5 py-4 text-ink outline-none ring-coral transition focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!hasSession || asking || !question.trim()}
          className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {asking ? "Generating answer..." : "Ask PDF"}
        </button>
      </form>
    </section>
  );
}

