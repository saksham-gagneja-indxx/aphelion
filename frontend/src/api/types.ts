// Shapes mirror what backend/api/routes.py actually returns.
// Verified against live responses from the Flask dev server.

export interface Reel {
  filename: string
  path: string
  size_bytes: number
  size_mb: number
  duration_seconds: number | null
  has_thumbnail: boolean
  thumbnail_path: string | null
  created_at: string
}

export interface UploadResponse {
  success: true
  message: string
  reel: Reel
}

export interface ApiStatus {
  app: string
  version: string
  environment: string
  debug: boolean
  database: string
  instagram_configured: boolean
  claude_configured: boolean
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  database?: string
  version?: string
  error?: string
}

/** Flask error responses are consistently `{ "error": "..." }`. */
export interface ApiError {
  error: string
}

/**
 * Response from GET /api/users/:id/analytics
 * Mirrors AnalyticsEngine.get_analytics_summary() in analytics_engine.py.
 * When no data exists the endpoint returns { message: "No analytics data available" }
 * rather than this shape — callers handle that via null.
 */
export interface AnalyticsSummary {
  total_posts_analyzed: number
  average_likes: number | null
  average_comments: number | null
  best_posting_hours: number[]
  best_posting_days: number[]
  peak_engagement_hour: number | null
  confidence: number
  last_updated: string | null
}

/** Response from GET /api/users/:id — subset we care about for Settings. */
export interface UserInfo {
  id: number
  instagram_username: string
  instagram_connected: boolean
  linkedin_connected: boolean
  timezone: string
  account_name: string | null
  is_active: boolean
  created_at: string | null
  last_login: string | null
}
