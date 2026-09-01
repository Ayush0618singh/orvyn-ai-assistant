import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  Attachment,
} from "@/types/attachment";


export async function uploadAttachments(
  files: File[]
): Promise<Attachment[]> {
  const formData =
    new FormData();


  for (const file of files) {
    formData.append(
      "files",
      file
    );
  }


  const response = await fetch(
    `${API_URL}/attachments`,
    {
      method: "POST",
      credentials: "include",
      body: formData,
    }
  );


  if (!response.ok) {
    throw new Error(
      await parseApiError(
        response
      )
    );
  }


  return response.json();
}


export async function deleteAttachment(
  attachmentId: string
): Promise<void> {
  const response = await fetch(
    `${API_URL}/attachments/${attachmentId}`,
    {
      method: "DELETE",
      credentials: "include",
    }
  );


  if (!response.ok) {
    throw new Error(
      await parseApiError(
        response
      )
    );
  }
}


export function getAttachmentUrl(
  attachmentId: string
): string {
  return (
    `${API_URL}/attachments/${attachmentId}`
  );
}