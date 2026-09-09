export interface WebSource {
  citation_id: string;

  title: string;

  url: string;

  domain: string;

  position: number;

  provider_score?: number | null;

  relevance_score: number;

  content: string;

  search_provider: string;
}