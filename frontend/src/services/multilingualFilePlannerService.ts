
export type MultilingualFileAction =
  | "propose_file"
  | "needs_clarification"
  | "no_action";

export interface MultilingualFilePlan {
  action: MultilingualFileAction;
  tool_name: string | null;
  filename: string | null;
  content: string | null;
  reason: string;
  requires_approval: boolean;
}

export interface ValidMultilingualFileProposal
  extends MultilingualFilePlan {
  action: "propose_file";
  tool_name: "workspace_file_write";
  filename: string;
  content: string;
  requires_approval: true;
}

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

const FILENAME_PATTERN =
  /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.txt$/;

const MAX_REQUEST_LENGTH = 8192;
const MAX_FILE_BYTES = 4096;

function isRecord(
  value: unknown
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function isValidAction(
  action: unknown
): action is MultilingualFileAction {
  return (
    action === "propose_file" ||
    action === "needs_clarification" ||
    action === "no_action"
  );
}

export function validateMultilingualFilePlan(
  value: unknown
): MultilingualFilePlan {
  if (!isRecord(value)) {
    throw new Error(
      "Invalid multilingual planning response."
    );
  }

  if (!isValidAction(value.action)) {
    throw new Error(
      "Unsupported multilingual planner action."
    );
  }

  if (typeof value.reason !== "string") {
    throw new Error(
      "Invalid multilingual planner reason."
    );
  }

  if (value.action !== "propose_file") {
    // A non-action response cannot carry executable
    // tool arguments into the application.
    return {
      action: value.action,
      tool_name: null,
      filename: null,
      content: null,
      reason: value.reason,
      requires_approval: false,
    };
  }

  if (
    value.tool_name !== "workspace_file_write" ||
    value.requires_approval !== true
  ) {
    throw new Error(
      "Untrusted tool proposal rejected."
    );
  }

  if (
    typeof value.filename !== "string" ||
    !FILENAME_PATTERN.test(value.filename)
  ) {
    throw new Error(
      "Invalid proposed filename."
    );
  }

  if (
    typeof value.content !== "string" ||
    value.content.trim().length === 0
  ) {
    throw new Error(
      "Invalid proposed file content."
    );
  }

  const contentBytes = new TextEncoder().encode(
    value.content
  ).length;

  if (contentBytes > MAX_FILE_BYTES) {
    throw new Error(
      "Proposed file content exceeds 4096 bytes."
    );
  }

  return {
    action: "propose_file",
    tool_name: "workspace_file_write",
    filename: value.filename,
    content: value.content,
    reason: value.reason,
    requires_approval: true,
  };
}

export function isValidMultilingualFileProposal(
  plan: MultilingualFilePlan
): plan is ValidMultilingualFileProposal {
  return (
    plan.action === "propose_file" &&
    plan.tool_name === "workspace_file_write" &&
    plan.requires_approval === true &&
    typeof plan.filename === "string" &&
    FILENAME_PATTERN.test(plan.filename) &&
    typeof plan.content === "string" &&
    plan.content.trim().length > 0 &&
    new TextEncoder().encode(
      plan.content
    ).length <= MAX_FILE_BYTES
  );
}

export async function planMultilingualFileAction(
  message: string,
  signal?: AbortSignal
): Promise<MultilingualFilePlan> {
  if (
    !message.trim() ||
    message.length > MAX_REQUEST_LENGTH
  ) {
    throw new Error(
      "Invalid multilingual planning request."
    );
  }

  const response = await fetch(
    `${API_URL}/agent/planning/multilingual-file`,
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
      }),
      cache: "no-store",
      signal,
    }
  );

  if (!response.ok) {
    let messageText =
      `AI planning failed (${response.status}).`;

    try {
      const body: unknown = await response.json();

      if (
        isRecord(body) &&
        typeof body.detail === "string"
      ) {
        messageText = body.detail;
      }
    } catch {
      // Preserve HTTP status if response is not JSON.
    }

    throw new Error(messageText);
  }

  const body: unknown = await response.json();

  return validateMultilingualFilePlan(body);
}
