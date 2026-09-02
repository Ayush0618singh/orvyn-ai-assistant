import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  IndexedDocument,
  IndexedDocumentDetail,
} from "@/types/document";


export async function indexAttachment(
  attachmentId: string
): Promise<IndexedDocumentDetail> {
  const response = await fetch(
    `${API_URL}/documents/from-attachment/${attachmentId}`,
    {
      method: "POST",
      credentials: "include",
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}


export async function getDocuments(): Promise<
  IndexedDocument[]
> {
  const response = await fetch(
    `${API_URL}/documents`,
    {
      method: "GET",
      credentials: "include",
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}


export async function getDocument(
  documentId: string
): Promise<IndexedDocumentDetail> {
  const response = await fetch(
    `${API_URL}/documents/${documentId}`,
    {
      method: "GET",
      credentials: "include",
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}


export async function deleteDocument(
  documentId: string
): Promise<void> {
  const response = await fetch(
    `${API_URL}/documents/${documentId}`,
    {
      method: "DELETE",
      credentials: "include",
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }
}