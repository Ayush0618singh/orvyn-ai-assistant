
import { API_URL } from "@/services/api";

export type YouTubeVideo = {
  video_id: string;
  title: string;
  channel_title: string;
  description: string;
  thumbnail_url: string;
  published_at: string;
  watch_url: string;
  embed_url: string;
};

type YouTubeSearchResponse = {
  query: string;
  count: number;
  videos: YouTubeVideo[];
};

export async function searchYouTubeVideos(
  query: string,
  limit = 10,
  signal?: AbortSignal,
): Promise<YouTubeSearchResponse> {
  const cleanedQuery = query.trim();

  if (!cleanedQuery) {
    throw new Error("Please enter a song, artist, or video to search.");
  }

  const params = new URLSearchParams({
    q: cleanedQuery,
    limit: String(Math.min(Math.max(limit, 1), 10)),
  });

  const response = await fetch(
    `${API_URL}/youtube/search?${params.toString()}`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal,
    },
  );

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : `YouTube search failed (${response.status}).`;

    throw new Error(detail);
  }

  return payload as YouTubeSearchResponse;
}
