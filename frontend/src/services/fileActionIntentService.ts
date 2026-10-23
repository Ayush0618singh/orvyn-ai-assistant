
export interface FileActionIntentResult {
  possibleFileAction: boolean;
  reason:
    | "explicit-file-request"
    | "not-file-request";
}

const ACTION_WORDS = [
  /\bcreate\b/i,
  /\bmake\b/i,
  /\bwrite\b/i,
  /\bsave\b/i,
  /\bgenerate\b/i,
  /\bbanao\b/i,
  /\bbana\s*do\b/i,
  /\bbana\s*kar\b/i,
  /\blikho\b/i,
  /\blikh\s*do\b/i,
  /\bfile\s*bna\b/i,
  /बनाओ/,
  /बना\s*दो/,
  /लिखो/,
  /लिख\s*दो/,
  /सेव\s*करो/,
];

const FILE_WORDS = [
  /\.txt\b/i,
  /\bfile\b/i,
  /\btext\s*document\b/i,
  /\btext\s*file\b/i,
  /\bnotes\s*file\b/i,
  /\bफाइल\b/i,
  /फ़ाइल/,
  /टेक्स्ट\s*फाइल/,
];

export function detectPossibleFileAction(
  message: string
): FileActionIntentResult {
  if (
    typeof message !== "string" ||
    !message.trim() ||
    message.length > 8192
  ) {
    return {
      possibleFileAction: false,
      reason: "not-file-request",
    };
  }

  const hasAction = ACTION_WORDS.some(
    (pattern) => pattern.test(message)
  );

  const hasFileReference = FILE_WORDS.some(
    (pattern) => pattern.test(message)
  );

  if (hasAction && hasFileReference) {
    return {
      possibleFileAction: true,
      reason: "explicit-file-request",
    };
  }

  return {
    possibleFileAction: false,
    reason: "not-file-request",
  };
}
