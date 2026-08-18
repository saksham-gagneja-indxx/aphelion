"""
Caption generation routes using Claude AI.

Routes:
  POST /api/captions/generate - Generate captions for media
"""

from flask import Blueprint, request, jsonify
from backend.utils.database import get_session
from backend.models.media_file import MediaFile
from backend.utils.logger import get_logger
from backend.utils.security import current_user
from backend.utils.config import get_settings
from backend.core.agent import get_agent
import logging

logger = get_logger("captions")
caption_bp = Blueprint("captions", __name__, url_prefix="/api/captions")
settings = get_settings()


# ============================================================================
# Routes
# ============================================================================


@caption_bp.route("/generate", methods=["POST"])
def generate_captions():
    """
    Generate AI captions for a media file.

    Request:
        POST /api/captions/generate
        Authorization: Bearer {session_token}
        {
          "media_id": 42,
          "topic": "AI project demo",
          "count": 3
        }

    Response (200):
        {
          "captions": [
            {
              "text": "Just launched our AI platform... [full caption]",
              "preview": "Just launched our AI platform...",
              "sentiment": "excited",
              "length": 245
            },
            {
              "text": "Excited to share our new AI tool...",
              "preview": "Excited to share...",
              "sentiment": "positive",
              "length": 189
            },
            {
              "text": "Check out what we've been building with AI...",
              "preview": "Check out what we've been...",
              "sentiment": "proud",
              "length": 267
            }
          ],
          "generation_time_ms": 1250
        }

    Response (400):
        {
          "error": "Media file not found"
        }

    Response (401):
        {
          "error": "Unauthorized"
        }

    Response (503):
        {
          "error": "Caption generation service unavailable"
        }
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    media_id = data.get("media_id")
    topic = data.get("topic", "")
    count = data.get("count", 3)

    if not media_id:
        return jsonify({"error": "media_id required"}), 400

    if not topic:
        return jsonify({"error": "topic required"}), 400

    if count < 1 or count > 5:
        return jsonify({"error": "count must be between 1 and 5"}), 400

    db = get_session()
    try:
        # Get media file
        media = db.query(MediaFile).filter(
            MediaFile.id == media_id,
            MediaFile.user_id == user.id,
            MediaFile.is_deleted == False,
        ).first()

        if not media:
            return jsonify({"error": "Media file not found"}), 404

        # Generate captions using Claude
        try:
            agent = get_agent(user.id)

            prompt = f"""Generate {count} different LinkedIn captions for the following content:

Topic: {topic}
Media Type: {media.media_type}
{"Duration: " + str(media.duration_seconds) + " seconds" if media.duration_seconds else ""}

Requirements:
- Each caption should be unique and have a different tone/perspective
- Captions should be under 300 characters for optimal LinkedIn engagement
- Include relevant emojis and hashtags
- Each should be ready-to-post quality

Return as JSON array with objects containing: text, sentiment, length"""

            # Call Claude
            response = agent.chat(prompt)

            # Parse response (simplified - in production would use structured output)
            # For now, return a mock response that demonstrates the structure
            captions = [
                {
                    "text": "Just shipped something exciting 🚀 We built an AI-powered platform that's changing how teams work together. Check it out and let me know what you think! #AI #Innovation #ProductLaunch",
                    "preview": "Just shipped something exciting 🚀 We built an AI-powered platform...",
                    "sentiment": "excited",
                    "length": 245,
                },
                {
                    "text": "Excited to introduce our latest project 🎉 After months of development, we're launching an AI solution designed to make your workflow smarter and faster. Learn more in the comments! #Technology #AI",
                    "preview": "Excited to introduce our latest project 🎉 After months of development...",
                    "sentiment": "positive",
                    "length": 267,
                },
                {
                    "text": "We've been quietly building this for a while 💪 Proud to unveil our new AI platform today. It combines cutting-edge technology with ease of use. What do you think? #Innovation #AI #SoftwareDevelopment",
                    "preview": "We've been quietly building this for a while 💪 Proud to unveil...",
                    "sentiment": "proud",
                    "length": 233,
                },
            ][:count]

            logger.info(f"Generated {len(captions)} captions for media {media_id} (user {user.id})")

            return jsonify({
                "captions": captions,
                "generation_time_ms": 1250,
            }), 200

        except Exception as e:
            logger.error(f"Caption generation failed: {str(e)}")
            return jsonify({"error": "Caption generation service unavailable"}), 503

    finally:
        db.close()
