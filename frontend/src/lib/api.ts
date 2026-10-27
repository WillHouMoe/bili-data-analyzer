import type { CreatorDetail, CreatorSummary, CreatorGrowth, CreatorAccountGrowth, VideoGrowth, QuerySummary, QueryDetail, VideoDetail, PaginatedVideos, StatsSummary, TrendPoint, InteractionData, VideoComparison, SettingsResponse, AIConversation, AIConversationDetail } from "@/types";

const BASE = import.meta.env.VITE_API_BASE || "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export const api = {
  fetch: (uid: number, start_date: string, end_date: string) =>
    request<{ query_id: number; uid: number; status: string }>("/fetch", {
      method: "POST", body: JSON.stringify({ uid, start_date, end_date }),
    }),
  getCreators: () => request<CreatorSummary[]>("/creators"),
  getCreator: (uid: number) => request<CreatorDetail>(`/creators/${uid}`),
  deleteCreator: (uid: number) => request(`/creators/${uid}`, { method: "DELETE" }),
  getCreatorVideos: (uid: number, params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    return request<PaginatedVideos>(`/creators/${uid}/videos?${qs}`);
  },
  getCreatorStatsSummary: (uid: number) =>
    request<StatsSummary>(`/creators/${uid}/stats/summary`),
  getCreatorTrend: (uid: number) =>
    request<TrendPoint[]>(`/creators/${uid}/stats/trend`),
  getCreatorInteraction: (uid: number) =>
    request<InteractionData>(`/creators/${uid}/stats/interaction`),
  getCreatorGrowth: (uid: number) =>
    request<CreatorGrowth>(`/creators/${uid}/stats/growth`),
  getCreatorAccountGrowth: (uid: number) =>
    request<CreatorAccountGrowth>(`/creators/${uid}/stats/account-growth`),
  refreshCreatorStats: (uid: number) =>
    request<{ status: string }>(`/creators/${uid}/stats/refresh`, {
      method: "POST",
    }),
  getCreatorComparison: (uid: number, bvid: string) =>
    request<VideoComparison>(`/creators/${uid}/videos/${bvid}/comparison`),
  getQueries: () => request<QuerySummary[]>("/queries"),
  getQuery: (id: number) => request<QueryDetail>(`/queries/${id}`),
  deleteQuery: (id: number) => request(`/queries/${id}`, { method: "DELETE" }),
  getVideos: (queryId: number, params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    return request<PaginatedVideos>(`/queries/${queryId}/videos?${qs}`);
  },
  getVideo: (bvid: string) => request<VideoDetail>(`/videos/${bvid}`),
  getVideoGrowth: (bvid: string) =>
    request<VideoGrowth>(`/videos/${bvid}/stats/growth`),
  getStatsSummary: (queryId: number) => request<StatsSummary>(`/queries/${queryId}/stats/summary`),
  getTrend: (queryId: number) => request<TrendPoint[]>(`/queries/${queryId}/stats/trend`),
  getInteraction: (queryId: number) => request<InteractionData>(`/queries/${queryId}/stats/interaction`),
  getComparison: (bvid: string, queryId: number) =>
    request<VideoComparison>(`/videos/${bvid}/stats/comparison?query_id=${queryId}`),
  getSettings: () => request<SettingsResponse>("/settings"),
  updateSettings: (data: Partial<SettingsResponse>) =>
    request<SettingsResponse>("/settings", { method: "PUT", body: JSON.stringify(data) }),
  testSessdata: (sessdata: string) =>
    request<{ status: string; message?: string }>("/settings/test-sessdata", {
      method: "POST",
      body: JSON.stringify({ sessdata }),
    }),
  testAi: (data: Pick<SettingsResponse, "ai_base_url" | "ai_api_key" | "ai_model">) =>
    request<{ status: string; message?: string }>("/settings/test-ai", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  aiAnalyzeUrl: (queryId: number) => `${BASE}/queries/${queryId}/ai/analyze`,

  // AI Conversations — query-scoped
  getAIConversations: (queryId: number) =>
    request<AIConversation[]>(`/queries/${queryId}/ai/conversations`),
  getAIConversation: (queryId: number, convId: number) =>
    request<AIConversationDetail>(`/queries/${queryId}/ai/conversations/${convId}`),
  deleteAIConversation: (queryId: number, convId: number) =>
    request(`/queries/${queryId}/ai/conversations/${convId}`, { method: "DELETE" }),
  createAIConversationUrl: (queryId: number) =>
    `${BASE}/queries/${queryId}/ai/conversations`,
  sendAIMessageUrl: (queryId: number, convId: number) =>
    `${BASE}/queries/${queryId}/ai/conversations/${convId}/messages`,

  // AI Conversations — creator-scoped
  getCreatorAIConversations: (uid: number) =>
    request<AIConversation[]>(`/creators/${uid}/ai/conversations`),
  getCreatorAIConversation: (uid: number, convId: number) =>
    request<AIConversationDetail>(`/creators/${uid}/ai/conversations/${convId}`),
  deleteCreatorAIConversation: (uid: number, convId: number) =>
    request(`/creators/${uid}/ai/conversations/${convId}`, { method: "DELETE" }),
  createCreatorAIConversationUrl: (uid: number) =>
    `${BASE}/creators/${uid}/ai/conversations`,
  sendCreatorAIMessageUrl: (uid: number, convId: number) =>
    `${BASE}/creators/${uid}/ai/conversations/${convId}/messages`,

  // AI Conversations — video-scoped
  getVideoAIConversations: (bvid: string) =>
    request<AIConversation[]>(`/videos/${bvid}/ai/conversations`),
  getVideoAIConversation: (bvid: string, convId: number) =>
    request<AIConversationDetail>(`/videos/${bvid}/ai/conversations/${convId}`),
  deleteVideoAIConversation: (bvid: string, convId: number) =>
    request(`/videos/${bvid}/ai/conversations/${convId}`, { method: "DELETE" }),
  createVideoAIConversationUrl: (bvid: string) =>
    `${BASE}/videos/${bvid}/ai/conversations`,
  sendVideoAIMessageUrl: (bvid: string, convId: number) =>
    `${BASE}/videos/${bvid}/ai/conversations/${convId}/messages`,

};
