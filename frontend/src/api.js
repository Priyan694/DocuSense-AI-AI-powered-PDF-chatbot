import axios from "axios";

const baseURL = import.meta.env.VITE_BACKEND_URL
  ? new URL("/api", import.meta.env.VITE_BACKEND_URL).toString()
  : "/api";

const api = axios.create({
  baseURL,
});

export const uploadPdf = async (files, llmProvider, sessionId) => {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("llm_provider", llmProvider);
  if (sessionId) {
    formData.append("session_id", sessionId);
  }
  const response = await api.post("/upload-pdf", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const askQuestion = async (payload) => {
  const response = await api.post("/ask", payload);
  return response.data;
};

export const runAction = async (payload) => {
  const response = await api.post("/action", payload);
  return response.data;
};

export const comparePdfs = async (payload) => {
  const response = await api.post("/compare", payload);
  return response.data;
};

export const resetSession = async (sessionId) => {
  const response = await api.post("/reset", { session_id: sessionId });
  return response.data;
};
