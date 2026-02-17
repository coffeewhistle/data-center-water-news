import unittest
from datetime import datetime, timedelta, timezone

from pipeline_utils import normalize_url, build_run_plan


class PipelineUtilsTests(unittest.TestCase):
    def test_normalize_url_drops_tracking_params(self):
        original = "HTTPS://Example.com/path/?utm_source=a&id=123&fbclid=zzz"
        normalized = normalize_url(original)
        self.assertEqual(normalized, "https://example.com/path?id=123")

    def test_backfill_window_plan(self):
        state = {
            "backfill_complete": False,
            "backfill_start_date": "2025-01-01",
            "backfill_end_date": "2025-01-31",
            "backfill_progress_cutoff": "2025-01-01",
        }
        plan = build_run_plan(state)
        self.assertEqual(plan["mode"], "backfill")
        self.assertEqual(plan["window_start"].isoformat(), "2025-01-01")
        self.assertEqual(plan["window_end"].isoformat(), "2025-01-07")
        self.assertFalse(plan["mark_backfill_complete"])

    def test_backfill_mark_complete_when_cutoff_past_end(self):
        state = {
            "backfill_complete": False,
            "backfill_start_date": "2025-01-01",
            "backfill_end_date": "2025-01-31",
            "backfill_progress_cutoff": "2025-02-01",
        }
        plan = build_run_plan(state)
        self.assertEqual(plan["mode"], "backfill")
        self.assertTrue(plan["mark_backfill_complete"])
        self.assertIsNone(plan["window_start"])
        self.assertIsNone(plan["window_end"])

    def test_daily_no_window_when_up_to_date(self):
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        state = {
            "backfill_complete": True,
            "last_daily_run_end": f"{yesterday}T23:59:59+00:00",
        }
        plan = build_run_plan(state)
        self.assertEqual(plan["mode"], "daily")
        self.assertIsNone(plan["window_start"])
        self.assertIsNone(plan["window_end"])


if __name__ == "__main__":
    unittest.main()
