export type UrlValidationResult =
  | {
      valid: true;
      url: URL;
      normalizedUrl: string;
    }
  | {
      valid: false;
      reason: string;
    };

export type SearchProvider =
  | "google"
  | "google_images"
  | "youtube";

const MAX_URL_LENGTH = 2048;
const MAX_QUERY_LENGTH = 500;

const ALLOWED_PROTOCOLS = new Set([
  "https:",
  "http:",
]);

const BLOCKED_HOSTS = new Set([
  "localhost",
  "localhost.localdomain",
  "metadata.google.internal",
  "metadata.google",
]);

function invalidUrl(reason: string): UrlValidationResult {
  return {
    valid: false,
    reason,
  };
}

function containsControlCharacters(value: string): boolean {
  return /[\u0000-\u001f\u007f-\u009f]/.test(value);
}

function isLocalHostname(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/\.$/, "");

  if (
    BLOCKED_HOSTS.has(host) ||
    host.endsWith(".localhost") ||
    host.endsWith(".local") ||
    host.endsWith(".internal")
  ) {
    return true;
  }

  // Block IPv4 literals in common private, loopback and link-local ranges.
  const ipv4Match = host.match(
    /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/,
  );

  if (ipv4Match) {
    const octets = ipv4Match.slice(1).map(Number);

    if (octets.some((octet) => octet < 0 || octet > 255)) {
      return true;
    }

    const [a, b] = octets;

    return (
      a === 0 ||
      a === 10 ||
      a === 127 ||
      (a === 169 && b === 254) ||
      (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && b === 168) ||
      a >= 224
    );
  }

  // Block IPv6 literals from this external-navigation utility.
  // This avoids accidental navigation to local IPv6 destinations.
  if (host.startsWith("[") || host.includes(":")) {
    return true;
  }

  return false;
}

export function validateExternalUrl(
  rawUrl: string,
): UrlValidationResult {
  if (typeof rawUrl !== "string") {
    return invalidUrl("The destination URL must be text.");
  }

  const value = rawUrl.trim();

  if (!value) {
    return invalidUrl("A destination URL is required.");
  }

  if (value.length > MAX_URL_LENGTH) {
    return invalidUrl("The URL is too long.");
  }

  if (containsControlCharacters(value)) {
    return invalidUrl(
      "The URL contains invalid control characters.",
    );
  }

  // Require an explicit HTTP(S) scheme rather than guessing the destination.
  if (!/^https?:\/\//i.test(value)) {
    return invalidUrl(
      "Enter a complete URL beginning with https:// or http://.",
    );
  }

  let url: URL;

  try {
    url = new URL(value);
  } catch {
    return invalidUrl("The destination URL is malformed.");
  }

  if (!ALLOWED_PROTOCOLS.has(url.protocol.toLowerCase())) {
    return invalidUrl(
      "Only HTTP and HTTPS destinations are allowed.",
    );
  }

  if (!url.hostname) {
    return invalidUrl("The URL must contain a hostname.");
  }

  if (url.username || url.password) {
    return invalidUrl(
      "URLs containing embedded credentials are not allowed.",
    );
  }

  const hostname = url.hostname
    .toLowerCase()
    .replace(/\.$/, "");

  if (
    !hostname.includes(".") ||
    hostname.startsWith(".") ||
    hostname.endsWith(".")
  ) {
    return invalidUrl(
      "The URL must contain a valid public hostname.",
    );
  }

  if (isLocalHostname(hostname)) {
    return invalidUrl(
      "Local and private network destinations are not allowed by this external URL handler.",
    );
  }

  // Avoid accepting whitespace or backslashes in the original authority.
  const authorityMatch = value.match(/^https?:\/\/([^/?#]*)/i);
  const authority = authorityMatch?.[1] ?? "";

  if (
    !authority ||
    /[\s\\]/.test(authority) ||
    authority.includes("@")
  ) {
    return invalidUrl(
      "The URL authority contains invalid or ambiguous characters.",
    );
  }

  url.hostname = hostname;

  return {
    valid: true,
    url,
    normalizedUrl: url.toString(),
  };
}

export function buildSearchUrl(
  provider: SearchProvider,
  query: string,
): string {
  if (typeof query !== "string") {
    throw new Error("Search query must be text.");
  }

  const cleanQuery = query
    .normalize("NFKC")
    .replace(/\s+/g, " ")
    .trim();

  if (!cleanQuery) {
    throw new Error("Search query cannot be empty.");
  }

  if (cleanQuery.length > MAX_QUERY_LENGTH) {
    throw new Error(
      `Search query must be ${MAX_QUERY_LENGTH} characters or fewer.`,
    );
  }

  const encodedQuery = encodeURIComponent(cleanQuery);

  switch (provider) {
    case "google":
      return `https://www.google.com/search?q=${encodedQuery}`;

    case "google_images":
      return `https://www.google.com/search?tbm=isch&q=${encodedQuery}`;

    case "youtube":
      return `https://www.youtube.com/results?search_query=${encodedQuery}`;

    default: {
      const exhaustiveCheck: never = provider;

      throw new Error(
        `Unsupported search provider: ${exhaustiveCheck}`,
      );
    }
  }
}