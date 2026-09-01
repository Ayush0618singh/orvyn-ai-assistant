export interface Attachment {
  id: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
}


export interface PendingAttachment {
  localId: string;
  file: File;
}