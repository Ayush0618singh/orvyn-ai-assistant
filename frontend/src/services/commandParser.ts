import type {
  CommandActionKind,
  ParsedCommand,
} from "@/types/commandAction";

const MAX_COMMAND_LENGTH = 1000;

function createCommandId(): string {
  try {
    if (
      typeof globalThis.crypto !== "undefined" &&
      typeof globalThis.crypto.randomUUID === "function"
    ) {
      return globalThis.crypto.randomUUID();
    }
  } catch {
    // Use the fallback if the browser crypto API is unavailable.
  }

  return `cmd-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeText(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ").trim();
}

function makeCommand(
  originalText: string,
  kind: CommandActionKind,
  title: string,
  description: string,
  options: {
    query?: string;
    url?: string;
    requiresConfirmation?: boolean;
  } = {},
): ParsedCommand {
  return {
    id: createCommandId(),
    originalText,
    kind,
    title,
    description,
    query: options.query,
    url: options.url,
    requiresConfirmation: options.requiresConfirmation ?? false,
  };
}

function extractUrl(text: string): string | undefined {
  const match = text.match(
    /(?:https?:\/\/|www\.)[^\s<>"'`]+/i,
  );

  return match?.[0].replace(/[),.!?;]+$/g, "");
}

function extractQuery(
  text: string,
  patterns: RegExp[],
): string {
  let query = text;

  for (const pattern of patterns) {
    query = query.replace(pattern, " ");
  }

  return query
    .replace(/[.,!?;:]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^(?:for|about|of|ke|ka|ki|k|for the)\s+/i, "")
    .trim();
}

const CHAT_PATTERNS = [
  /\bhello\s+orvyn\b/i,
  /\bhi\s+orvyn\b/i,
  /\bintroduce yourself\b/i,
  /\btell me about yourself\b/i,
  /\bwho are you\b/i,
  /\btalk to orvyn\b/i,
  /\bopen chat(?: workspace)?\b/i,
  /\bchat with orvyn\b/i,
  /\bstart a conversation\b/i,
  /\bopen (?:the )?chat\b/i,
  /नमस्ते/i,
  /ओरविन से बात/i,
  /orvyn से बात/i,
  /चैट खोलो/i,
  /बात करो/i,
];

const YOUTUBE_PREFIX = [
  /\byoutube\b/gi,
  /यूट्यूब/gi,
  /\b(?:please|on|par|pe|mein|me|ko|ke liye)\b/gi,
  /\b(?:play|search|find|open|start|listen to|watch|show)\b/gi,
  /\b(?:song|songs|music|video|videos|track|tracks)\b/gi,
  /\b(?:chalao|chala do|bajao|lagao|sunao|suna do|dikhao|dhoondo|dhundo|karo)\b/gi,
  /(?:पर|पे|में|चलाओ|चला दो|बजाओ|लगा दो|सुनाओ|दिखाओ|ढूंढो|खोजो)/g,
];

const IMAGE_PREFIX = [
  /\b(?:google images?|images on google|image search|photos on google|pictures on google)\b/gi,
  /\b(?:show|find|search|give me|display|open|get|dikhao|dhoondo|dhundo)\b/gi,
  /\b(?:please|for me|some|the|of|on|par|pe|mein|me|ko|karo)\b/gi,
  /(?:गूगल|फोटो|फोटोज|तस्वीर|तस्वीरें|चित्र|दिखाओ|खोजो|ढूंढो)/g,
];

const WEB_PREFIX = [
  /\b(?:search the web|web search|search online|look up|google search|search|google|find online|browse for)\b/gi,
  /\b(?:please|for me|on google|in google|on the web|online|par|pe|mein|me|ko|karo|kijiye)\b/gi,
  /(?:गूगल|सर्च करो|सर्च करना|खोजो|ढूंढो|ढूँढो|पता करो)/g,
];

function isChatRequest(text: string): boolean {
  return CHAT_PATTERNS.some((pattern) => pattern.test(text));
}

function isImageRequest(text: string): boolean {
  return (
    /\b(?:google images?|image search|photos on google|pictures on google)\b/i.test(
      text,
    ) ||
    /(?:गूगल.*(?:फोटो|तस्वीर|चित्र)|(?:फोटो|तस्वीर|चित्र).*गूगल)/i.test(
      text,
    )
  );
}

function isYoutubeRequest(text: string): boolean {
  return /\byoutube\b|यूट्यूब/i.test(text);
}

function isMusicRequest(text: string): boolean {
  return (
    /\b(?:song|songs|music|track|tracks|play|listen|bajao|chalao|sunao)\b/i.test(
      text,
    ) ||
    /(?:गाना|गाने|संगीत|बजाओ|चलाओ|सुनाओ)/i.test(text)
  );
}

function isSearchRequest(text: string): boolean {
  return (
    /\b(?:search|find|look up|google|show|give me|display|browse|dikhao|dhoondo|dhundo)\b/i.test(
      text,
    ) ||
    /(?:खोजो|ढूंढो|दिखाओ|पता करो|निकालो|सर्च)/i.test(text)
  );
}

function createUnsupported(
  originalText: string,
  title: string,
  description: string,
): ParsedCommand {
  return makeCommand(
    originalText,
    "unsupported",
    title,
    description,
  );
}

export function parseCommand(input: string): ParsedCommand {
  const originalText = normalizeText(input);

  if (!originalText) {
    return createUnsupported(
      "",
      "Empty command",
      "Enter or speak a command before continuing.",
    );
  }

  if (originalText.length > MAX_COMMAND_LENGTH) {
    return createUnsupported(
      originalText,
      "Command too long",
      `Commands must be ${MAX_COMMAND_LENGTH} characters or fewer.`,
    );
  }

  const text = originalText.toLowerCase();

  // Handle explicit chat requests before generic search intents.
  if (isChatRequest(originalText)) {
    return makeCommand(
      originalText,
      "chat_request",
      "Open Chat Workspace",
      "Open the ORVYN chat interface to continue the conversation.",
    );
  }

  // External URLs always require confirmation.
  const url = extractUrl(originalText);

  if (url) {
    return makeCommand(
      originalText,
      "open_url",
      "Open external URL",
      "Review the destination carefully. The execution layer must validate the URL and request confirmation before opening it.",
      {
        url,
        requiresConfirmation: true,
      },
    );
  }

  // Check specific search types before generic web search.
  if (isImageRequest(text)) {
    const query = extractQuery(originalText, IMAGE_PREFIX);

    if (!query) {
      return createUnsupported(
        originalText,
        "Image search needs a topic",
        "Tell ORVYN which image, photo or subject you want to find.",
      );
    }

    return makeCommand(
      originalText,
      "google_images",
      "Search Google Images",
      "Prepare a Google Images search for the requested subject.",
      { query },
    );
  }

  if (isYoutubeRequest(text)) {
    const query = extractQuery(originalText, YOUTUBE_PREFIX);

    if (!query) {
      return createUnsupported(
        originalText,
        "YouTube search needs a topic",
        "Say which song, artist or video you want to find.",
      );
    }

    return makeCommand(
      originalText,
      "youtube_search",
      isMusicRequest(text)
        ? "Find music on YouTube"
        : "Search YouTube",
      isMusicRequest(text)
        ? "Search YouTube for matching music. Playback depends on video availability and browser restrictions."
        : "Search YouTube for the requested topic.",
      { query },
    );
  }

  if (isSearchRequest(text)) {
    const query = extractQuery(originalText, WEB_PREFIX);

    if (!query) {
      return createUnsupported(
        originalText,
        "Search needs a topic",
        "Tell ORVYN what you want to search for on the web.",
      );
    }

    return makeCommand(
      originalText,
      "web_search",
      "Search the web",
      "Prepare a Google web search for the requested topic.",
      { query },
    );
  }

  return createUnsupported(
    originalText,
    "Command not recognised",
    "Try a YouTube search, Google Images search, web search, external URL or Chat Workspace request.",
  );
}