"""
Optimal posting time calculation for LinkedIn.

Uses historical analytics data to determine best times to post
for maximum engagement.
"""

from datetime import datetime, time, timedelta
from backend.utils.logger import get_logger

logger = get_logger("optimal_timing")


class OptimalTimingCalculator:
    """Calculate optimal posting times based on audience engagement patterns."""

    # LinkedIn engagement peaks by day of week (0=Monday, 6=Sunday)
    # Based on LinkedIn's published best practices
    WEEKDAY_SCORES = {
        0: 0.85,  # Monday - strong engagement
        1: 0.90,  # Tuesday - peak engagement
        2: 0.88,  # Wednesday - peak engagement
        3: 0.87,  # Thursday - strong engagement
        4: 0.82,  # Friday - moderate engagement
        5: 0.60,  # Saturday - low engagement
        6: 0.55,  # Sunday - low engagement
    }

    # Optimal hours for posting (in 24-hour format)
    # Based on when professionals are most active
    OPTIMAL_HOURS = {
        7: 0.40,   # 7 AM - early starters
        8: 0.65,   # 8 AM - morning commute
        9: 0.85,   # 9 AM - office start
        10: 0.90,  # 10 AM - peak morning activity
        11: 0.88,  # 11 AM - late morning
        12: 0.70,  # 12 PM - lunch break
        13: 0.60,  # 1 PM - post-lunch
        14: 0.65,  # 2 PM - afternoon activity
        15: 0.80,  # 3 PM - afternoon peak
        16: 0.85,  # 4 PM - late afternoon
        17: 0.75,  # 5 PM - end of day
        18: 0.50,  # 6 PM - commute home
    }

    @classmethod
    def calculate_optimal_time(cls, user_analytics: dict = None, days_ahead: int = 3) -> datetime:
        """
        Calculate the optimal time to post.

        Args:
            user_analytics: User's historical engagement data (optional)
            days_ahead: How many days in advance to schedule (default: 3)

        Returns:
            datetime object for optimal posting time in UTC
        """
        if user_analytics is None:
            user_analytics = {}

        # Use custom analytics if available, otherwise use defaults
        weekday_scores = user_analytics.get("weekday_scores", cls.WEEKDAY_SCORES)
        optimal_hours = user_analytics.get("optimal_hours", cls.OPTIMAL_HOURS)

        # Find best day in the next N days
        best_day = cls._find_best_day(days_ahead, weekday_scores)

        # Find best hour in that day
        best_hour = cls._find_best_hour(optimal_hours)

        # Combine date and time
        optimal_datetime = datetime.combine(
            best_day,
            time(hour=best_hour, minute=0, second=0)
        )

        logger.info(f"Calculated optimal posting time: {optimal_datetime}")
        return optimal_datetime

    @classmethod
    def _find_best_day(cls, days_ahead: int, weekday_scores: dict) -> datetime:
        """Find the best day in the next N days based on weekday engagement."""
        from backend.utils.timeutil import utcnow

        best_day = None
        best_score = 0
        now = utcnow()

        for i in range(1, days_ahead + 1):
            candidate_day = now + timedelta(days=i)
            day_of_week = candidate_day.weekday()
            score = weekday_scores.get(day_of_week, 0.5)

            if score > best_score:
                best_score = score
                best_day = candidate_day

        return best_day.date() if best_day else (now + timedelta(days=1)).date()

    @classmethod
    def _find_best_hour(cls, optimal_hours: dict) -> int:
        """Find the best hour to post."""
        best_hour = max(optimal_hours.items(), key=lambda x: x[1])[0]
        return best_hour

    @classmethod
    def get_all_optimal_slots(
        cls, user_analytics: dict = None, days_ahead: int = 7, top_n: int = 5
    ) -> list:
        """
        Get top N optimal posting slots in the next N days.

        Args:
            user_analytics: User's historical engagement data
            days_ahead: Number of days to consider
            top_n: Return top N slots

        Returns:
            List of dicts with datetime and score
        """
        if user_analytics is None:
            user_analytics = {}

        weekday_scores = user_analytics.get("weekday_scores", cls.WEEKDAY_SCORES)
        optimal_hours = user_analytics.get("optimal_hours", cls.OPTIMAL_HOURS)

        slots = []
        from backend.utils.timeutil import utcnow

        now = utcnow()

        for day_offset in range(1, days_ahead + 1):
            candidate_day = now + timedelta(days=day_offset)
            day_of_week = candidate_day.weekday()
            day_score = weekday_scores.get(day_of_week, 0.5)

            for hour, hour_score in optimal_hours.items():
                combined_score = day_score * hour_score
                slot_datetime = datetime.combine(
                    candidate_day.date(),
                    time(hour=hour, minute=0, second=0)
                )

                slots.append({
                    "datetime": slot_datetime,
                    "score": combined_score,
                    "day_of_week": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
                        day_of_week
                    ],
                    "hour": hour,
                })

        # Sort by score descending and return top N
        slots.sort(key=lambda x: x["score"], reverse=True)
        return slots[:top_n]

    @classmethod
    def adjust_for_timezone(cls, datetime_obj: datetime, timezone: str) -> datetime:
        """
        Adjust posting time for user's timezone.

        Args:
            datetime_obj: UTC datetime
            timezone: User's timezone (e.g., 'America/New_York')

        Returns:
            Adjusted datetime in user's timezone
        """
        try:
            import pytz

            tz = pytz.timezone(timezone)
            utc_tz = pytz.UTC

            # Localize to UTC and convert to user timezone
            utc_datetime = utc_tz.localize(datetime_obj)
            local_datetime = utc_datetime.astimezone(tz)

            return local_datetime
        except Exception as e:
            logger.warning(f"Timezone adjustment failed: {e}, returning UTC time")
            return datetime_obj
