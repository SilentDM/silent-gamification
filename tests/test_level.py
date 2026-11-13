"""The level reflects only the last 100 days: habit average (missing days = 0) + extras fading over 100 days."""
import unittest
from datetime import date, timedelta

from test_database import DbTestCase  # noqa: F401  (also sets up sys.path)

import database as db  # noqa: E402

TODAY = date(2026, 11, 13)


def log(aid, d, status, score):
    iso = d.isocalendar()
    db.save_log(aid, iso[0], iso[1], iso[2] - 1, status, score)


def add_xp(d, amount, ref):
    conn = db.get_connection()
    db._ledger_set(conn.cursor(), "event", ref, d.isoformat(), amount, replace=False)
    conn.commit()
    conn.close()


class LevelTests(DbTestCase):
    def setUp(self):
        super().setUp()
        self.gym = db.add_activity("Gym")

    def test_nothing_yet_is_level_1(self):
        lv = db.get_level(TODAY)
        self.assertEqual((lv["level"], lv["score"]), (1, 0.0))

    def test_a_perfect_100_days_is_level_100(self):
        for back in range(100):
            log(self.gym, TODAY - timedelta(days=back), "Excellent", 10)
        lv = db.get_level(TODAY)
        self.assertAlmostEqual(lv["habit_points"], 100.0)
        self.assertEqual(lv["level"], 100)

    def test_missing_days_pull_the_level_down(self):
        for back in range(1, 100):  # every day except today (still open: it doesn't count)
            log(self.gym, TODAY - timedelta(days=back), "Ok", 7)
        self.assertAlmostEqual(db.get_level(TODAY)["habit_points"], 70.0)
        # ten days later with nothing marked: the ten empty days count as 0
        lv = db.get_level(TODAY + timedelta(days=10))
        self.assertAlmostEqual(lv["habit_points"], 7 * 89 / 99 * 10, places=4)
        self.assertLess(lv["level"], 70)

    def test_rest_only_days_are_neutral(self):
        for back in range(1, 100):
            if back % 10 == 0:
                log(self.gym, TODAY - timedelta(days=back), db.REST_STATUS, None)
            else:
                log(self.gym, TODAY - timedelta(days=back), "Ok", 7)
        self.assertAlmostEqual(db.get_level(TODAY)["habit_points"], 70.0)

    def test_old_answers_leave_the_window(self):
        log(self.gym, TODAY - timedelta(days=100), "Excellent", 10)  # 101 days including today: outside
        self.assertEqual(db.get_level(TODAY)["habit_points"], 0.0)

    def test_extras_fade_to_zero_over_100_days(self):
        add_xp(TODAY, 100, "a")  # 100 XP = 10 points today
        self.assertAlmostEqual(db.get_level(TODAY)["extra_points"], 10.0)
        self.assertAlmostEqual(db.get_level(TODAY + timedelta(days=50))["extra_points"], 5.0)
        self.assertAlmostEqual(db.get_level(TODAY + timedelta(days=99))["extra_points"], 0.1)
        self.assertEqual(db.get_level(TODAY + timedelta(days=100))["extra_points"], 0.0)
        self.assertEqual(db.get_level(TODAY - timedelta(days=1))["extra_points"], 0.0)  # not earned yet

    def test_score_is_capped_and_lifetime_xp_kept(self):
        for back in range(100):
            log(self.gym, TODAY - timedelta(days=back), "Excellent", 10)
        add_xp(TODAY, 300, "big")
        lv = db.get_level(TODAY)
        self.assertEqual((lv["score"], lv["level"], lv["progress"]), (100.0, 100, 1.0))
        self.assertGreater(lv["total_xp"], 300)  # the lifetime counter is still there
        self.assertEqual(lv["rank"], "Centurion")


if __name__ == "__main__":
    unittest.main()
