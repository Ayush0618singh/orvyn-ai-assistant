
export function getCommandErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    const message = error.message.trim();

    if (message) {
      return message.slice(0, 300);
    }
  }

  if (typeof error === "string" && error.trim()) {
    return error.trim().slice(0, 300);
  }

  return "The command could not be completed. Please try again.";
}

export function getCommandSuccessMessage(action: string): string {
  const normalizedAction = action.trim();

  return normalizedAction
    ? `${normalizedAction} completed successfully.`
    : "Command completed successfully.";
}
