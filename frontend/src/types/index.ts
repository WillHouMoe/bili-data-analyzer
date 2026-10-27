export interface QuerySummary {
  id: number; uid: number; user_name: string | null;
  start_date: string; end_date: string; status: string;
  progress: string | null; video_count: number; total_views: number;
  created_at: string;
}

export interface QueryDetail extends QuerySummary {
  error_message: string | null;
  total_likes: number; total_coins: number; total_favorites: number;
  total_shares: number; total_danmaku: number; total_comments: number;
}

export interface CreatorSummary {
  uid: number;
  name: string;
  avatar_url: string | null;
  start_date: string | null;
  end_date: string | null;
  video_count: number;
  query_count: number;
  total_views: number;
  followers: number | null;
  following: number | null;
  creator_total_views: number | null;
  creator_total_likes: number | null;
  archive_count: number | null;
  profile_stats_updated_at: string | null;
  last_fetched_at: string | null;
  last_stats_refresh_at: string | null;
  refresh_status: string;
  refresh_progress: string | null;
  refresh_error: string | null;
  status: string;
  progress: string | null;
  error_message: string | null;
}

export interface CreatorDetail extends CreatorSummary {
  total_likes: number;
  total_coins: number;
  total_favorites: number;
  total_shares: number;
  total_danmaku: number;
  total_comments: number;
  rankings: RankingMatch[];
}

export interface VideoStats {
  views: number; likes: number; coins: number; favorites: number;
  shares: number; danmaku_count: number; comment_count: number;
  interaction_rate: number;
}

export interface VideoSummary {
  bvid: string; title: string; cover_url: string | null;
  duration: number; published_at: string | null;
  tags: string | null; stats: VideoStats;
}

export interface VideoDetail extends VideoSummary {
  description: string | null;
  rankings: RankingMatch[];
}

export interface RankingMatch {
  kind: "popular" | "weekly";
  period: string;
  period_name: string | null;
  rank: number;
  bvid: string;
  title: string;
  views: number;
  likes: number;
  fetched_at: string;
  in_library: boolean;
}

export interface PaginatedVideos {
  items: VideoSummary[]; total: number;
  page: number; page_size: number; total_pages: number;
}

export interface StatsSummary {
  total_views: number; total_likes: number; total_coins: number;
  total_favorites: number; total_shares: number; total_danmaku: number;
  total_comments: number; video_count: number;
}

export interface TrendPoint { date: string; views: number; }
export interface InteractionData { likes: number; coins: number; favorites: number; shares: number; }
export interface VideoComparison {
  metrics: string[]; video_values: number[];
  average_values: number[]; percentage_diff: number[];
  max_values: number[];
}

export interface GrowthPoint {
  key: string;
  min_days: number;
  max_days: number | null;
  median_views: number;
  p25_views: number;
  p75_views: number;
  samples: number;
}

export interface GrowthTimelinePoint {
  fetched_at: string;
  median_views: number;
  p25_views: number;
  p75_views: number;
  samples: number;
}

export interface CreatorGrowth {
  points: GrowthPoint[];
  timeline: GrowthTimelinePoint[];
  video_count: number;
  observation_count: number;
  videos_with_history: number;
  first_snapshot_at: string | null;
  last_snapshot_at: string | null;
}

export interface VideoGrowthPoint {
  fetched_at: string;
  views: number;
  likes: number;
  interaction_rate: number;
}

export interface VideoGrowth {
  bvid: string;
  points: VideoGrowthPoint[];
}

export interface AccountGrowthPoint {
  fetched_at: string;
  followers: number | null;
  total_views: number | null;
  total_likes: number | null;
}

export interface CreatorAccountGrowth {
  uid: number;
  points: AccountGrowthPoint[];
}

export interface SettingsResponse {
  sessdata: string; ai_base_url: string;
  ai_api_key: string; ai_model: string;
  proxy_list: string;
  refresh_window_size: number;
}

// AI Conversation Types

export interface AIPreset {
  id: string;
  labelKey: string;
  descriptionKey: string;
  icon: string;
}

export interface AIConversation {
  id: number;
  preset: string;
  title: string | null;
  created_at: string;
  updated_at: string | null;
  message_count: number;
}

export interface ToolCallInfo {
  name: string;
  arguments: Record<string, unknown>;
  result?: string | null;
}

export interface AIMessageItem {
  id: number;
  role: "user" | "assistant";
  content: string | null;
  tool_calls?: ToolCallInfo[] | null;
  created_at: string;
}

export interface AIConversationDetail {
  id: number;
  preset: string;
  title: string | null;
  uid: number | null;
  query_id: number | null;
  bvid: string | null;
  messages: AIMessageItem[];
}
