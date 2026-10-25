
"use client";

import { useCallback, useEffect, useState } from "react";
import { getDocuments } from "@/services/documentService";
import { retrieveRAGContext } from "@/services/ragService";
import type { IndexedDocument } from "@/types/document";
import type { RAGSource } from "@/types/rag";

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "Unknown size";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleDateString();
}

function statusClasses(status: IndexedDocument["status"]): string {
  if (status === "ready") return "border-emerald-800 bg-emerald-950/50 text-emerald-300";
  if (status === "processing") return "border-amber-800 bg-amber-950/40 text-amber-300";
  return "border-red-900 bg-red-950/40 text-red-300";
}

export default function KnowledgeCenterPanel() {
  const [documents, setDocuments] = useState<IndexedDocument[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [documentsError, setDocumentsError] = useState("");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [sources, setSources] = useState<RAGSource[]>([]);
  const [searched, setSearched] = useState(false);

  const loadDocuments = useCallback(async (signal?: AbortSignal) => {
    setLoadingDocuments(true);
    setDocumentsError("");

    try {
      const result = await getDocuments();
      if (!signal?.aborted) setDocuments(result);
    } catch (error) {
      if (!signal?.aborted) {
        setDocumentsError(
          error instanceof Error ? error.message : "Unable to load documents.",
        );
      }
    } finally {
      if (!signal?.aborted) setLoadingDocuments(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadDocuments(controller.signal);
    return () => controller.abort();
  }, [loadDocuments]);

  async function handleSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!query.trim() || searching) return;

    setSearching(true);
    setSearchError("");
    setSources([]);
    setSearched(false);

    try {
      const result = await retrieveRAGContext({ query: query.trim() });
      setSources(result.sources);
      setSearched(true);
    } catch (error) {
      setSearchError(
        error instanceof Error ? error.message : "Knowledge search failed.",
      );
    } finally {
      setSearching(false);
    }
  }

  const readyCount = documents.filter((doc) => doc.status === "ready").length;
  const processingCount = documents.filter((doc) => doc.status === "processing").length;
  const failedCount = documents.filter((doc) => doc.status === "failed").length;

  return (
    <section className="rounded-2xl border border-cyan-900/40 bg-[#07111d]/90 p-5 shadow-[0_0_35px_rgba(6,182,212,0.05)] sm:p-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
            ORVYN / KNOWLEDGE ENGINE
          </p>
          <h2 className="mt-2 text-xl font-semibold text-white sm:text-2xl">
            Knowledge Center
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">
            Search your indexed documents using ORVYN&apos;s existing retrieval API.
          </p>
        </div>

        <button
          type="button"
          onClick={() => void loadDocuments()}
          disabled={loadingDocuments}
          className="rounded-xl border border-cyan-900/70 px-4 py-2 text-sm text-cyan-300 transition hover:bg-cyan-950/50 disabled:opacity-50"
        >
          {loadingDocuments ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <p className="text-xs text-slate-500">Ready to search</p>
          <p className="mt-2 text-2xl font-semibold text-emerald-300">{readyCount}</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <p className="text-xs text-slate-500">Processing</p>
          <p className="mt-2 text-2xl font-semibold text-amber-300">{processingCount}</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <p className="text-xs text-slate-500">Failed</p>
          <p className="mt-2 text-2xl font-semibold text-red-300">{failedCount}</p>
        </div>
      </div>

      <form onSubmit={handleSearch} className="mt-5">
        <label htmlFor="orvyn-knowledge-query" className="mb-2 block text-sm font-medium text-slate-300">
          Ask your knowledge base
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id="orvyn-knowledge-query"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            maxLength={2000}
            placeholder="e.g. Summarize the main points in my document..."
            className="min-w-0 flex-1 rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-700"
          />
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="rounded-xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {searching ? "Searching..." : "Search"}
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Search runs against documents already indexed and available to your account.
        </p>
      </form>

      {documentsError && (
        <p role="alert" className="mt-4 rounded-xl border border-red-900/70 bg-red-950/30 p-3 text-sm text-red-300">
          Documents: {documentsError}
        </p>
      )}

      {searchError && (
        <p role="alert" className="mt-4 rounded-xl border border-red-900/70 bg-red-950/30 p-3 text-sm text-red-300">
          Search: {searchError}
        </p>
      )}

      <div className="mt-6">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-white">Indexed Documents</h3>
          <span className="text-xs text-slate-500">{documents.length} total</span>
        </div>

        {loadingDocuments ? (
          <p className="rounded-xl border border-slate-800 p-5 text-sm text-slate-500">
            Loading documents...
          </p>
        ) : documents.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 p-6 text-center">
            <p className="text-sm font-medium text-slate-300">No indexed documents yet</p>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              Upload a supported file and index it through ORVYN&apos;s existing file workflow.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {documents.map((document) => (
              <article
                key={document.id}
                className="flex flex-col gap-3 rounded-xl border border-slate-800/90 bg-slate-950/50 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="break-words text-sm font-medium text-slate-200">
                    {document.name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {formatBytes(document.size_bytes)} · Updated {formatDate(document.updated_at)}
                  </p>
                  {document.status === "failed" && document.error_message && (
                    <p className="mt-2 break-words text-xs text-red-300">
                      {document.error_message}
                    </p>
                  )}
                </div>
                <span className={`w-fit shrink-0 rounded-full border px-3 py-1 text-xs ${statusClasses(document.status)}`}>
                  {document.status}
                </span>
              </article>
            ))}
          </div>
        )}
      </div>

      {searched && (
        <div className="mt-7">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-white">Retrieved Sources</h3>
            <span className="text-xs text-slate-500">{sources.length} matches</span>
          </div>

          {sources.length === 0 ? (
            <div className="rounded-xl border border-slate-800 p-5 text-sm text-slate-400">
              No matching document chunks were returned. Try a more specific question or check that your documents are indexed.
            </div>
          ) : (
            <div className="space-y-3">
              {sources.map((source) => (
                <article
                  key={`${source.document_id}-${source.chunk_id}`}
                  className="rounded-xl border border-cyan-950/70 bg-slate-950/70 p-4"
                >
                  <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
                    <div className="min-w-0">
                      <p className="break-words text-sm font-medium text-cyan-300">
                        {source.document_name}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Chunk {source.chunk_index + 1}
                      </p>
                    </div>
                    <span className="w-fit rounded-full border border-slate-800 px-2.5 py-1 text-xs text-slate-300">
                      Similarity {(source.similarity * 100).toFixed(1)}%
                    </span>
                  </div>
                  <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-300">
                    {source.content}
                  </p>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
