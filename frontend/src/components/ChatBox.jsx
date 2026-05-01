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

function IntentBadge({ intent, answerMode }) {
  if (!intent && !answerMode) {
    return null;
  }

  return (
    <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-[0.16em]">
      {answerMode ? (
        <span className="rounded-full bg-sky/10 px-3 py-1 text-sky">
          {answerMode === "strict_pdf" ? "Strict PDF mode" : "Explanation mode"}
        </span>
      ) : null}
      {intent ? <span className="rounded-full bg-gold/15 px-3 py-1 text-ink">Intent: {intent}</span> : null}
    </div>
  );
}

function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[92%] rounded-[28px] px-5 py-4 shadow-sm ${
          isUser
            ? "bg-ink text-white"
            : "border border-white/70 bg-white/92 text-ink shadow-float"
        }`}
      >
        <p className="whitespace-pre-wrap leading-7">{message.content}</p>
        {!isUser ? (
          <>
            <IntentBadge intent={message.intent} answerMode={message.answerMode} />
            {message.confidence != null ? (
              <p className="mt-3 text-xs text-slate">
                Confidence: {message.confidence}
                {message.weakContext ? " · retrieved context is weak" : ""}
              </p>
            ) : null}
            {message.rewrittenQuestion ? (
              <p className="mt-2 text-xs text-slate">Rewritten query: {message.rewrittenQuestion}</p>
            ) : null}
            <SourceReferences sources={message.sources} />
          </>
        ) : null}
      </div>
    </div>
  );
}

export default function ChatBox({
  messages,
  onAsk,
  onAction,
  asking,
  hasSession,
  llmProvider,
  answerModePreference,
  setAnswerModePreference,
  uploadedPdfCount,
}) {
  const [question, setQuestion] = useState("");

  const modeButtons = [
    { value: "auto", label: "Auto" },
    { value: "strict_pdf", label: "Strict PDF" },
    { value: "explanation", label: "Explanation" },
  ];

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }
    await onAsk(question);
    setQuestion("");
  };

  return (
    <section className="flex min-h-[820px] flex-col rounded-[34px] border border-white/70 bg-white/75 p-6 shadow-panel backdrop-blur">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-moss">Chat Workspace</p>
          <h2 className="font-display text-2xl text-ink">Ask factual or explanation-based questions</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate">
            Strict PDF mode is used for factual questions. Explanation mode uses the PDF first and clearly labels any additional knowledge.
          </p>
        </div>
        <div className="rounded-full border border-sky/10 bg-mist px-4 py-2 text-sm text-slate">Model: {llmProvider}</div>
      </div>

      <div className="mb-5 rounded-[28px] border border-ink/8 bg-white/75 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-ink">Answer mode</p>
            <p className="mt-1 text-sm text-slate">
              Auto uses intent detection. You can also force strict document-only or explanation-first behavior.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {modeButtons.map((mode) => (
              <button
                key={mode.value}
                type="button"
                onClick={() => setAnswerModePreference(mode.value)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  answerModePreference === mode.value
                    ? "bg-ink text-white"
                    : "border border-ink/8 bg-white text-ink hover:border-sky/40 hover:bg-mist"
                }`}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {actionButtons.map((action) => (
          <button
            key={action.key}
            onClick={() => onAction(action.key)}
            disabled={!hasSession || asking || (action.key === "compare" && uploadedPdfCount < 2)}
            className="rounded-full border border-ink/8 bg-white px-4 py-2 text-sm font-medium text-ink transition hover:border-gold/60 hover:bg-gold/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {action.label}
          </button>
        ))}
      </div>
      {hasSession && uploadedPdfCount < 2 ? (
        <p className="mb-4 text-sm text-slate">Upload at least two PDFs to enable comparison.</p>
      ) : null}

      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {messages.length === 0 ? (
          <div className="rounded-[28px] border border-dashed border-sky/20 bg-gradient-to-br from-white via-mist/60 to-gold/10 p-8">
            <p className="font-display text-2xl text-ink">Ready when you are</p>
            <p className="mt-3 max-w-xl text-sm leading-7 text-slate">
              Upload a PDF, read the generated summary on the left, then ask for explanations, examples, comparisons, or direct factual answers from the document.
            </p>
          </div>
        ) : null}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {asking ? (
          <div className="flex justify-start">
            <div className="rounded-[24px] border border-white/70 bg-white/90 px-5 py-4 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-coral" />
                <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-gold [animation-delay:140ms]" />
                <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-moss [animation-delay:280ms]" />
              </div>
              <p className="mt-3 text-sm text-slate">DocuSense AI is thinking…</p>
            </div>
          </div>
        ) : null}
      </div>

      <form onSubmit={handleSubmit} className="mt-5 space-y-3">
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask what the PDF says, or ask for explanation, example, comparison, importance, advantages, disadvantages..."
          disabled={!hasSession || asking}
          className="h-32 w-full resize-none rounded-[28px] border border-white/80 bg-white/90 px-5 py-4 text-ink outline-none ring-sky transition focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate">
            {hasSession
              ? answerModePreference === "auto"
                ? "The assistant will detect the question intent before answering."
                : answerModePreference === "strict_pdf"
                  ? "Strict PDF mode is forced for this question."
                  : "Explanation mode is forced for this question."
              : "Upload a PDF to activate the chat."}
          </p>
          <button
            type="submit"
            disabled={!hasSession || asking || !question.trim()}
            className="rounded-full bg-coral px-5 py-3 text-sm font-semibold text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {asking ? "Generating answer..." : "Ask DocuSense"}
          </button>
        </div>
      </form>
    </section>
  );
}
