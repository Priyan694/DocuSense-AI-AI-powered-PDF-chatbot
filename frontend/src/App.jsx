import { useState } from "react";
import { askQuestion, resetSession, runAction, uploadPdf } from "./api";
import ChatBox from "./components/ChatBox";
import SummaryCard from "./components/SummaryCard";
import UploadPDF from "./components/UploadPDF";

let messageId = 0;

export default function App() {
  const [files, setFiles] = useState([]);
  const [llmProvider, setLlmProvider] = useState("minimax");
  const [sessionId, setSessionId] = useState("");
  const [summary, setSummary] = useState("");
  const [warning, setWarning] = useState("");
  const [pdfNames, setPdfNames] = useState([]);
  const [chunkCount, setChunkCount] = useState(0);
  const [messages, setMessages] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);

  const appendMessage = (message) => {
    messageId += 1;
    setMessages((current) => [...current, { id: messageId, ...message }]);
  };

  const handleUpload = async () => {
    try {
      setUploading(true);
      const data = await uploadPdf(files, llmProvider);
      setSessionId(data.session_id);
      setSummary(data.summary);
      setWarning(data.warning || "");
      setPdfNames(data.pdf_names || []);
      setChunkCount(data.chunk_count || 0);
      setMessages([]);
    } catch (error) {
      appendMessage({
        role: "assistant",
        content: error.response?.data?.detail || "Upload failed.",
        sources: [],
      });
    } finally {
      setUploading(false);
    }
  };

  const handleAsk = async (question) => {
    appendMessage({ role: "user", content: question, sources: [] });
    try {
      setAsking(true);
      const data = await askQuestion({
        session_id: sessionId,
        question,
        llm_provider: llmProvider,
      });
      appendMessage({
        role: "assistant",
        content: data.answer,
        sources: data.sources,
        confidence: data.confidence,
        weakContext: data.weak_context,
        rewrittenQuestion: data.rewritten_question,
      });
    } catch (error) {
      appendMessage({
        role: "assistant",
        content: error.response?.data?.detail || "Question answering failed.",
        sources: [],
      });
    } finally {
      setAsking(false);
    }
  };

  const handleAction = async (action) => {
    const compareInstruction =
      action === "compare"
        ? "Compare the uploaded PDFs or major sections if only one PDF is available."
        : null;

    appendMessage({
      role: "user",
      content: `Run action: ${action}`,
      sources: [],
    });

    try {
      setAsking(true);
      const data = await runAction({
        session_id: sessionId,
        action,
        llm_provider: llmProvider,
        compare_instruction: compareInstruction,
      });
      appendMessage({
        role: "assistant",
        content: data.content,
        sources: data.sources,
      });
    } catch (error) {
      appendMessage({
        role: "assistant",
        content: error.response?.data?.detail || "Action failed.",
        sources: [],
      });
    } finally {
      setAsking(false);
    }
  };

  const handleReset = async () => {
    if (!sessionId) {
      setFiles([]);
      setSummary("");
      setWarning("");
      setPdfNames([]);
      setChunkCount(0);
      setMessages([]);
      return;
    }

    try {
      await resetSession(sessionId);
    } catch (error) {
      console.error(error);
    } finally {
      setSessionId("");
      setFiles([]);
      setSummary("");
      setWarning("");
      setPdfNames([]);
      setChunkCount(0);
      setMessages([]);
    }
  };

  return (
    <main className="min-h-screen px-4 py-8 text-ink md:px-8">
      <div className="mx-auto grid max-w-7xl gap-6 xl:grid-cols-[1.02fr_1.2fr]">
        <div className="space-y-6">
          <UploadPDF
            files={files}
            setFiles={setFiles}
            llmProvider={llmProvider}
            setLlmProvider={setLlmProvider}
            onUpload={handleUpload}
            loading={uploading}
            onReset={handleReset}
            hasSession={Boolean(sessionId)}
          />
          <SummaryCard
            summary={summary}
            warning={warning}
            pdfNames={pdfNames}
            chunkCount={chunkCount}
          />
        </div>

        <ChatBox
          messages={messages}
          onAsk={handleAsk}
          onAction={handleAction}
          asking={asking}
          hasSession={Boolean(sessionId)}
          llmProvider={llmProvider}
        />
      </div>
    </main>
  );
}

