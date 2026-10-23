
import { cookies } from "next/headers";
import {
  NextRequest,
  NextResponse,
} from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const COOKIE_NAME =
  "orvyn_access_token";

const ALLOWED_ACTIONS = new Set([
  "approve",
  "deny",
  "execute",
]);

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const MAX_REQUEST_BYTES = 12000;

type RouteContext = {
  params: Promise<{
    segments: string[];
  }>;
};

function errorResponse(
  message: string,
  status: number
): NextResponse {
  return NextResponse.json(
    {
      detail: message,
    },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
      },
    }
  );
}

function resolveBackendUrl(
  segments: string[]
): string | null {
  const configured =
    process.env.NEXT_PUBLIC_API_URL;

  if (!configured) {
    return null;
  }

  const base =
    configured.replace(/\/+$/, "");

  // Existing workspace approval creation.
  if (
    segments.length === 1 &&
    segments[0] === "workspace-file"
  ) {
    return (
      `${base}/tool-approvals/workspace-file`
    );
  }

  // Conversation-linked approval creation.
  if (
    segments.length === 2 &&
    segments[0] === "chat" &&
    segments[1] === "workspace-file"
  ) {
    return (
      `${base}/chat-tool-approvals/workspace-file`
    );
  }

  // Existing approve / deny / execute.
  if (
    segments.length === 2 &&
    UUID_PATTERN.test(
      segments[0]
    ) &&
    ALLOWED_ACTIONS.has(
      segments[1]
    )
  ) {
    const approvalId =
      encodeURIComponent(
        segments[0]
      );

    const action =
      segments[1];

    return (
      `${base}/tool-approvals/${approvalId}/${action}`
    );
  }

  // Never proxy arbitrary paths.
  return null;
}

function isWorkspaceCreation(
  segments: string[]
): boolean {
  return (
    (
      segments.length === 1 &&
      segments[0] === "workspace-file"
    ) ||
    (
      segments.length === 2 &&
      segments[0] === "chat" &&
      segments[1] === "workspace-file"
    )
  );
}

function isChatWorkspaceCreation(
  segments: string[]
): boolean {
  return (
    segments.length === 2 &&
    segments[0] === "chat" &&
    segments[1] === "workspace-file"
  );
}

function isPlainObject(
  value: unknown
): value is Record<string, unknown> {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value)
  );
}

function validateCreationPayload(
  parsed: Record<string, unknown>,
  chatCreation: boolean
): string | null {
  const allowedKeys =
    new Set(
      chatCreation
        ? [
            "conversation_id",
            "message_id",
            "filename",
            "content",
          ]
        : [
            "filename",
            "content",
          ]
    );

  for (
    const key of Object.keys(
      parsed
    )
  ) {
    if (
      !allowedKeys.has(key)
    ) {
      return (
        "Unsupported request field."
      );
    }
  }

  if (
    typeof parsed.filename !==
      "string" ||
    !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\.txt$/.test(
      parsed.filename
    )
  ) {
    return "Invalid filename.";
  }

  if (
    typeof parsed.content !==
      "string" ||
    parsed.content.length < 1 ||
    parsed.content.length > 4096 ||
    new TextEncoder()
      .encode(
        parsed.content
      ).length > 4096
  ) {
    return "Invalid file content.";
  }

  if (
    chatCreation
  ) {
    if (
      typeof parsed.conversation_id !==
        "string" ||
      !UUID_PATTERN.test(
        parsed.conversation_id
      )
    ) {
      return (
        "Invalid conversation ID."
      );
    }

    if (
      parsed.message_id !== undefined &&
      (
        typeof parsed.message_id !==
          "string" ||
        !UUID_PATTERN.test(
          parsed.message_id
        )
      )
    ) {
      return (
        "Invalid message ID."
      );
    }
  }

  return null;
}

export async function POST(
  request: NextRequest,
  context: RouteContext
): Promise<NextResponse> {
  // Explicit same-origin protection.
  const origin =
    request.headers.get(
      "origin"
    );

  if (
    origin !==
    request.nextUrl.origin
  ) {
    return errorResponse(
      "Cross-origin action rejected.",
      403
    );
  }

  const fetchSite =
    request.headers.get(
      "sec-fetch-site"
    );

  if (
    fetchSite &&
    fetchSite !== "same-origin"
  ) {
    return errorResponse(
      "Cross-site action rejected.",
      403
    );
  }

  const {
    segments,
  } = await context.params;

  const backendUrl =
    resolveBackendUrl(
      segments
    );

  if (
    !backendUrl
  ) {
    return errorResponse(
      "Unsupported approval action or API configuration.",
      400
    );
  }

  const cookieStore =
    await cookies();

  const accessToken =
    cookieStore
      .get(
        COOKIE_NAME
      )
      ?.value;

  if (
    !accessToken
  ) {
    return errorResponse(
      "Please sign in again.",
      401
    );
  }

  const creationRequest =
    isWorkspaceCreation(
      segments
    );

  let requestBody:
    string | undefined;

  if (
    creationRequest
  ) {
    const contentType =
      request.headers.get(
        "content-type"
      ) ?? "";

    if (
      !contentType
        .toLowerCase()
        .startsWith(
          "application/json"
        )
    ) {
      return errorResponse(
        "JSON content type required.",
        415
      );
    }

    // Check declared size before reading.
    const contentLength =
      request.headers.get(
        "content-length"
      );

    if (
      contentLength &&
      Number(
        contentLength
      ) > MAX_REQUEST_BYTES
    ) {
      return errorResponse(
        "Request body too large.",
        413
      );
    }

    try {
      requestBody =
        await request.text();
    } catch {
      return errorResponse(
        "Could not read request body.",
        400
      );
    }

    if (
      new TextEncoder()
        .encode(
          requestBody
        ).length >
      MAX_REQUEST_BYTES
    ) {
      return errorResponse(
        "Request body too large.",
        413
      );
    }

    let parsed: unknown;

    try {
      parsed =
        JSON.parse(
          requestBody
        );
    } catch {
      return errorResponse(
        "Invalid JSON.",
        400
      );
    }

    if (
      !isPlainObject(
        parsed
      )
    ) {
      return errorResponse(
        "Invalid request body.",
        400
      );
    }

    const validationError =
      validateCreationPayload(
        parsed,
        isChatWorkspaceCreation(
          segments
        )
      );

    if (
      validationError
    ) {
      return errorResponse(
        validationError,
        422
      );
    }
  } else {
    // No caller-supplied arguments for
    // approve / deny / execute.
    const rawBody =
      await request.text();

    if (
      rawBody.length > 0
    ) {
      return errorResponse(
        "This action does not accept a request body.",
        400
      );
    }
  }

  try {
    const backendResponse =
      await fetch(
        backendUrl,
        {
          method: "POST",
          headers: {
            Authorization:
              `Bearer ${accessToken}`,
            Accept:
              "application/json",
            ...(creationRequest
              ? {
                  "Content-Type":
                    "application/json",
                }
              : {}),
          },
          body: requestBody,
          cache: "no-store",
          redirect: "manual",
          signal:
            AbortSignal.timeout(
              15000
            ),
        }
      );

    // Never follow backend redirects.
    if (
      backendResponse.status >= 300 &&
      backendResponse.status < 400
    ) {
      return errorResponse(
        "Unexpected backend redirect.",
        502
      );
    }

    const responseText =
      await backendResponse.text();

    return new NextResponse(
      responseText,
      {
        status:
          backendResponse.status,
        headers: {
          "Content-Type":
            "application/json",
          "Cache-Control":
            "no-store",
        },
      }
    );
  } catch {
    return errorResponse(
      "Could not contact the ORVYN backend.",
      502
    );
  }
}
