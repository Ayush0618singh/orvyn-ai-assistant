
import { API_URL, parseApiError } from "@/services/api";
import type { RAGSource } from "@/types/rag";

export interface RAGQueryResponse {
  query: string;
  sources: RAGSource[];
}

export interface RAGQueryPayload {
  query: string;
  document_ids?: string[];
}

export async function retrieveRAGContext(
  payload: RAGQueryPayload,
  signal?: AbortSignal,
): Promise<RAGQueryResponse> {
  const query = payload.query.trim();

  if (!query) {
    throw new Error("Please enter a question to search your knowledge base.");
  }

  const response = await fetch(`${API_URL}/rag/retrieve`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      query,
      ...(payload.document_ids?.length
        ? { document_ids: payload.document_ids }
        : {}),
    }),
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const result: unknown = await response.json();

  if (
    !result ||
    typeof result !== "object" ||
    !("query" in result) ||
    !("sources" in result) ||
    !Array.isArray(result.sources)
  ) {
    throw new Error("Invalid response received from RAG API.");
  }

  return result as RAGQueryResponse;
}
