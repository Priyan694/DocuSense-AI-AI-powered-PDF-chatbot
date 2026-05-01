import { useState } from "react";
import { askQuestion, comparePdfs, resetSession, runAction, uploadPdf } from "./api";
import ChatBox from "./components/ChatBox";
import KeyConceptsCard from "./components/KeyConceptsCard";
import PDFStatusCard from "./components/PDFStatusCard";
import SummaryCard from "./components/SummaryCard";
import UploadPDF from "./components/UploadPDF";

let messageId = 0;

export default function App() {
  const [files, setFiles] = useState([]);
  const [llmProvider, setLlmProvider] = useState("minimax");
  const [answerModePreference, setAnswerModePreference] = useState("auto");
  const [sessionId, setSessionId] = useState("");
  const [summary, setSummary] = useState("");
  const [summaryDetails, setSummaryDetails] = useState(null);
  const [keyConcepts, setKeyConcepts] = useState([]);
  const [warning, setWarning] = useState("");
  const [uploadedPdfs, setUploadedPdfs] = useState([]);
  const [pdfNames, setPdfNames] = useState([]);
  const [uploadedPdfCount, setUploadedPdfCount] = useState(0);
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
      const data = await uploadPdf(files, llmProvider, sessionId || undefined);
      setSessionId(data.session_id);
      setSummary(data.summary);
      setSummaryDetails(data.summary_details || null);
      setKeyConcepts(data.key_concepts || data.summary_details?.key_concepts || []);
      setWarning(data.warning || "");
      setUploadedPdfs(data.uploaded_pdfs || []);
      setPdfNames(data.pdf_names || []);
      setUploadedPdfCount(data.uploaded_pdf_count || 0);
      setChunkCount(data.chunk_count || 0);
      setFiles([]);
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
        answer_mode_preference: answerModePreference,
      });
      appendMessage({
        role: "assistant",
        content: data.answer,
        sources: data.sources,
        confidence: data.confidence,
        weakContext: data.weak_context,
        rewrittenQuestion: data.rewritten_question,
        intent: data.intent,
        answerMode: data.answer_mode,
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

    if (action === "compare" && uploadedPdfCount < 2) {
      appendMessage({
        role: "assistant",
        content: "Please upload at least one more PDF to compare.",
        sources: [],
      });
      return;
    }

    appendMessage({
      role: "user",
      content: `Run action: ${action}`,
      sources: [],
    });

    try {
      setAsking(true);
      const data =
        action === "compare"
          ? await comparePdfs({
              session_id: sessionId,
              llm_provider: llmProvider,
              compare_instruction: compareInstruction,
            })
          : await runAction({
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
      setSummaryDetails(null);
      setKeyConcepts([]);
      setWarning("");
      setUploadedPdfs([]);
      setPdfNames([]);
      setUploadedPdfCount(0);
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
      setSummaryDetails(null);
      setKeyConcepts([]);
      setWarning("");
      setUploadedPdfs([]);
      setPdfNames([]);
      setUploadedPdfCount(0);
      setChunkCount(0);
      setMessages([]);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden px-4 py-8 text-ink md:px-8">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-8rem] top-12 h-72 w-72 rounded-full bg-sky/12 blur-3xl" />
        <div className="absolute right-[-4rem] top-28 h-80 w-80 rounded-full bg-coral/12 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-gold/12 blur-3xl" />
      </div>

      <div className="relative mx-auto grid max-w-[1500px] gap-6 xl:grid-cols-[430px_minmax(0,1fr)]">
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
            pdfNames={pdfNames}
            uploadedPdfCount={uploadedPdfCount}
            chunkCount={chunkCount}
          />
          <PDFStatusCard
            sessionId={sessionId}
            uploadedPdfs={uploadedPdfs}
            chunkCount={chunkCount}
            warning={warning}
            uploading={uploading}
          />
          <SummaryCard
            summary={summary}
            summaryDetails={summaryDetails}
            warning={warning}
            pdfNames={pdfNames}
            chunkCount={chunkCount}
          />
          <KeyConceptsCard keyConcepts={keyConcepts} />
        </div>

          <ChatBox
            messages={messages}
            onAsk={handleAsk}
            onAction={handleAction}
            asking={asking}
            hasSession={Boolean(sessionId)}
            llmProvider={llmProvider}
            answerModePreference={answerModePreference}
            setAnswerModePreference={setAnswerModePreference}
            uploadedPdfCount={uploadedPdfCount}
          />
      </div>
    </main>
  );
}
