
import type { WorkspaceFileRequest } from "@/types/toolApproval";

const FILENAME_PATTERN =
  /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.txt$/;

export type FileCommandResult =
  | { kind: "not_command" }
  | { kind: "invalid"; error: string }
  | {
      kind: "valid";
      payload: WorkspaceFileRequest;
    };

export function parseChatFileCommand(
  message: string
): FileCommandResult {
  if (!/^\/file(?=\s|$)/i.test(message)) {
    return { kind: "not_command" };
  }

  const body = message.replace(/^\/file\s*/i, "");
  const separator = body.indexOf("|");

  if (separator === -1) {
    return {
      kind: "invalid",
      error:
        "Correct format: /file filename.txt | File content",
    };
  }

  const filename = body.slice(0, separator).trim();
  const content = body.slice(separator + 1).trim();

  if (!FILENAME_PATTERN.test(filename)) {
    return {
      kind: "invalid",
      error:
        "Only simple .txt filenames are allowed. No folders or paths.",
    };
  }

  if (!content) {
    return {
      kind: "invalid",
      error: "File content cannot be empty.",
    };
  }

  const bytes = new TextEncoder().encode(content).length;

  if (bytes > 4096) {
    return {
      kind: "invalid",
      error: "Maximum file content is 4096 UTF-8 bytes.",
    };
  }

  return {
    kind: "valid",
    payload: { filename, content },
  };
}
