
"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  searchYouTubeVideos,
  type YouTubeVideo,
} from "@/services/youtubeService";

export default function YouTubePlayer() {
  const [query, setQuery] = useState("");
  const [videos, setVideos] = useState<YouTubeVideo[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<YouTubeVideo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    return () => {
      // Stop playback when this player component unmounts.
      setSelectedVideo(null);
    };
  }, []);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const cleanedQuery = query.trim();

    if (!cleanedQuery) {
      setError("Song, artist ya video ka naam likho.");
      return;
    }

    setLoading(true);
    setError("");
    setNotice("");
    setVideos([]);

    try {
      const result = await searchYouTubeVideos(cleanedQuery, 10);

      setVideos(result.videos);

      if (result.videos.length === 0) {
        setSelectedVideo(null);
        setNotice("Koi embeddable video nahi mila. Dusra search try karo.");
        return;
      }

      setSelectedVideo(result.videos[0]);
      setNotice(
        "Video load ho gaya. Agar autoplay block ho, player ke andar Play dabao.",
      );
    } catch (cause) {
      setSelectedVideo(null);
      setError(
        cause instanceof Error
          ? cause.message
          : "YouTube search abhi complete nahi ho saka.",
      );
    } finally {
      setLoading(false);
    }
  }

  function playVideo(video: YouTubeVideo) {
    setSelectedVideo(video);
    setNotice("Video player mein load ho raha hai.");
  }

  const playerUrl = selectedVideo
    ? `${selectedVideo.embed_url}?autoplay=1&playsinline=1&rel=0`
    : "";

  return (
    <section className="w-full space-y-4 rounded-2xl border border-cyan-400/20 bg-slate-950/80 p-4 text-slate-100 shadow-xl shadow-cyan-950/20 sm:p-5">
      <header className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-red-500/15 text-xl">
          ▶
        </div>
        <div>
          <h2 className="text-lg font-semibold">ORVYN Music</h2>
          <p className="text-sm text-slate-400">
            Search YouTube and play videos
          </p>
        </div>
      </header>

      <form onSubmit={handleSearch} className="flex flex-col gap-2 sm:flex-row">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          maxLength={200}
          placeholder="Arijit Singh songs, lo-fi music..."
          aria-label="Search YouTube videos"
          className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm outline-none transition focus:border-cyan-400"
        />

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded-xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Searching..." : "Search & Play"}
        </button>
      </form>

      {error && (
        <p
          role="alert"
          className="rounded-lg border border-red-400/30 bg-red-950/30 p-3 text-sm text-red-200"
        >
          {error}
        </p>
      )}

      {notice && (
        <p role="status" className="text-sm text-slate-400">
          {notice}
        </p>
      )}

      {selectedVideo && (
        <div className="space-y-3">
          <div className="aspect-video overflow-hidden rounded-xl border border-slate-800 bg-black">
            <iframe
              key={selectedVideo.video_id}
              src={playerUrl}
              title={`YouTube player: ${selectedVideo.title}`}
              className="h-full w-full"
              allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
              referrerPolicy="strict-origin-when-cross-origin"
              allowFullScreen
            />
          </div>

          <div>
            <h3 className="font-medium leading-6">{selectedVideo.title}</h3>
            <p className="mt-1 text-sm text-slate-400">
              {selectedVideo.channel_title}
            </p>
            <a
              href={selectedVideo.watch_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block text-sm text-cyan-300 underline underline-offset-4 hover:text-cyan-200"
            >
              Open on YouTube
            </a>
          </div>
        </div>
      )}

      {videos.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-300">
            Search results ({videos.length})
          </h3>

          <div className="grid gap-2">
            {videos.map((video) => {
              const isSelected =
                selectedVideo?.video_id === video.video_id;

              return (
                <button
                  key={video.video_id}
                  type="button"
                  onClick={() => playVideo(video)}
                  className={`flex w-full items-center gap-3 rounded-xl border p-2 text-left transition ${
                    isSelected
                      ? "border-cyan-400/60 bg-cyan-400/10"
                      : "border-slate-800 bg-slate-900/70 hover:border-slate-600"
                  }`}
                >
                  {video.thumbnail_url ? (
                    // YouTube supplies these thumbnail URLs in its API response.
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={video.thumbnail_url}
                      alt=""
                      loading="lazy"
                      className="h-16 w-28 shrink-0 rounded-lg object-cover"
                    />
                  ) : (
                    <div className="flex h-16 w-28 shrink-0 items-center justify-center rounded-lg bg-slate-800">
                      ▶
                    </div>
                  )}

                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 block text-sm font-medium">
                      {video.title}
                    </span>
                    <span className="mt-1 block truncate text-xs text-slate-400">
                      {video.channel_title}
                    </span>
                  </span>

                  <span className="px-2 text-cyan-300">
                    {isSelected ? "Playing" : "▶"}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
