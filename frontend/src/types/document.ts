export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  character_count: number;
}

export interface IndexedDocument {
  id: string;
  attachment_id: string | null;
  name: string;
  mime_type: string;
  size_bytes: number;
  status: "processing" | "ready" | "failed";
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface IndexedDocumentDetail
  extends IndexedDocument {
  chunks: DocumentChunk[];
}