
export interface CommandExample {
  id: string;
  label: string;
  command: string;
  category: "youtube" | "web" | "chat" | "navigation";
}

export const COMMAND_EXAMPLES: CommandExample[] = [
  {
    id: "youtube-songs",
    label: "Search YouTube songs",
    command: "YouTube par Arijit Singh ke songs search karo",
    category: "youtube",
  },
  {
    id: "youtube-python",
    label: "Find Python tutorials",
    command: "YouTube par Python tutorials search karo",
    category: "youtube",
  },
  {
    id: "web-orvyn",
    label: "Research agentic AI",
    command: "Search ORVYN agentic AI on Google",
    category: "web",
  },
  {
    id: "chat-intro",
    label: "Talk to ORVYN",
    command: "Hello ORVYN, introduce yourself",
    category: "chat",
  },
  {
    id: "open-command-center",
    label: "Open command center",
    command: "Open ORVYN command center",
    category: "navigation",
  },
];

export function getCommandExample(id: string): CommandExample | undefined {
  return COMMAND_EXAMPLES.find((example) => example.id === id);
}
