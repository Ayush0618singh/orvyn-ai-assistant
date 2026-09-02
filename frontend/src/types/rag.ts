export interface RAGSource {
  chunk_id: string;

  document_id: string;

  document_name: string;

  chunk_index: number;

  position?: number;

  similarity: number;

  content: string;
}