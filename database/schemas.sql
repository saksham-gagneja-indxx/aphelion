-- ============================================
-- Social Media Automation Agent - Database Schema
-- ============================================
-- This file contains the SQL schema for the database
-- Can be used for manual setup or reference
-- SQLAlchemy will auto-generate tables from models

-- ============ USERS TABLE ============
-- Stores Instagram and LinkedIn account information
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instagram_username VARCHAR(255) UNIQUE NOT NULL,
    instagram_session_id VARCHAR(500),
    instagram_user_id VARCHAR(255),
    instagram_connected BOOLEAN DEFAULT FALSE,
    linkedin_email VARCHAR(255),
    linkedin_session_id VARCHAR(500),
    linkedin_connected BOOLEAN DEFAULT FALSE,
    timezone VARCHAR(50) DEFAULT 'Asia/Kolkata',
    account_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    preferences JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    instagram_connected_at TIMESTAMP,
    linkedin_connected_at TIMESTAMP
);

-- ============ POSTS TABLE ============
-- Stores information about scheduled and posted reels
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    video_path VARCHAR(500) NOT NULL,
    video_url VARCHAR(500),
    thumbnail_path VARCHAR(500),
    video_duration FLOAT,
    video_size INTEGER,
    caption TEXT,
    hashtags VARCHAR(500),
    ai_generated_caption BOOLEAN DEFAULT FALSE,
    ai_generated_hashtags BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'draft',
    platform VARCHAR(50) DEFAULT 'instagram',
    scheduled_time TIMESTAMP,
    posted_at TIMESTAMP,
    instagram_post_id VARCHAR(255),
    linkedin_post_id VARCHAR(255),
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    engagement_rate FLOAT,
    metadata JSON,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    job_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============ ANALYTICS TABLE ============
-- Stores engagement analytics and optimal posting times
CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    analysis_type VARCHAR(50) DEFAULT 'hourly',
    platform VARCHAR(50) DEFAULT 'instagram',
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    best_posting_hours JSON,
    best_posting_days JSON,
    hourly_analytics JSON,
    daily_analytics JSON,
    weekly_analytics JSON,
    total_posts_analyzed INTEGER DEFAULT 0,
    average_likes FLOAT,
    average_comments FLOAT,
    average_shares FLOAT,
    average_engagement_rate FLOAT,
    trending_hashtags JSON,
    trending_content_themes JSON,
    posting_frequency_optimal INTEGER,
    peak_engagement_hour INTEGER,
    peak_engagement_day INTEGER,
    slowest_hour INTEGER,
    slowest_day INTEGER,
    follower_growth_rate FLOAT,
    engagement_growth_rate FLOAT,
    data_source VARCHAR(100) DEFAULT 'instagram_api',
    last_analysis_posts_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_calculated_at TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============ INDEXES ============
-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_time ON posts(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_posts_job_id ON posts(job_id);
CREATE INDEX IF NOT EXISTS idx_analytics_user_id ON analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_users_instagram_username ON users(instagram_username);

-- ============ VIEWS (Optional) ============
-- Useful queries as views

-- View: Recent posts for a user
CREATE VIEW IF NOT EXISTS vw_recent_posts AS
SELECT
    p.id,
    p.user_id,
    u.instagram_username,
    p.caption,
    p.status,
    p.platform,
    p.scheduled_time,
    p.posted_at,
    p.likes,
    p.comments,
    p.views,
    p.engagement_rate,
    p.created_at
FROM posts p
JOIN users u ON p.user_id = u.id
ORDER BY p.created_at DESC;

-- View: Posting performance by hour
CREATE VIEW IF NOT EXISTS vw_performance_by_hour AS
SELECT
    strftime('%H', posted_at) as hour,
    COUNT(*) as posts_count,
    AVG(likes) as avg_likes,
    AVG(comments) as avg_comments,
    AVG(engagement_rate) as avg_engagement,
    MAX(views) as max_views
FROM posts
WHERE posted_at IS NOT NULL
GROUP BY hour
ORDER BY avg_engagement DESC;

-- ============ SEED DATA (Optional) ============
-- Uncomment to add sample data

-- INSERT INTO users (instagram_username, timezone)
-- VALUES ('demo_account', 'Asia/Kolkata');
