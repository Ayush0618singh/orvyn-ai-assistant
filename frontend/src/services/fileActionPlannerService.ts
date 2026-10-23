
import { API_URL } from "@/services/api";

export interface FileActionPlan {
  recognized: boolean;
  tool_name: string | null;
  filename: string | null;
  content: string | null;
  requires_approval: boolean;
  message: string;
}

interface FilePlanRequest {
  message: string;
}

export async function planNaturalLanguageFileAction(
  message: string,
  signal?: AbortSignal
): Promise<FileActionPlan> {
  const payload: FilePlanRequest = {
    message,
  };

  const response = await fetch(
    `${API_URL}/agent/planning/file`,
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal,
      cache: "no-store",
    }
  );

  if (!response.ok) {
    let detail = `Planning failed (${response.status}).`;

    try {
      const body: unknown = await response.json();

      if (
        typeof body === "object" &&
        body !== null &&
        "detail" in body &&
        typeof body.detail === "string"
      ) {
        detail = body.detail;
      }
    } catch {
      // Keep the HTTP status error.
    }

    throw new Error(detail);
  }

  const data: unknown = await response.json();

  if (
    typeof data !== "object" ||
    data === null ||
    !("recognized" in data) ||
    typeof data.recognized !== "boolean"
  ) {
    throw new Error(
      "Invalid planning response from ORVYN."
    );
  }

  return data as FileActionPlan;
}

export function isSafeFileActionPlan(
  plan: FileActionPlan
): plan is FileActionPlan & {
  tool_name: "workspace_file_write";
  filename: string;
  content: string;
  requires_approval: true;
} {
  const filenamePattern =
    /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.txt$/;

  return (
    plan.recognized === true &&
    plan.tool_name === "workspace_file_write" &&
    plan.requires_approval === true &&
    typeof plan.filename === "string" &&
    filenamePattern.test(plan.filename) &&
    typeof plan.content === "string" &&
    plan.content.length > 0 &&
    new TextEncoder().encode(plan.content).length <=
      4096
  );
}
