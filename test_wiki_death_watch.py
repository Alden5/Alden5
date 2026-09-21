import datetime
import email.utils
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import wiki_death_watch as watch


class DetectionTests(unittest.TestCase):
    def test_current_living_style_is_not_detected(self) -> None:
        html = """
        <table class="infobox">
          <tr><th class="infobox-label">Born</th><td>June 14, 1946</td></tr>
        </table>
        <p><b>Donald John Trump</b> (born June 14, 1946) is an American politician.</p>
        """
        detected, reasons, lead = watch.detect_death_notice(html)
        self.assertFalse(detected)
        self.assertEqual(reasons, [])
        self.assertIn("is an American", lead)

    def test_infobox_died_row_is_detected(self) -> None:
        html = """
        <table class="infobox">
          <tr><th class="infobox-label">Died</th>
          <td><span>September 21, 2026</span> (aged 80)</td></tr>
        </table>
        <p>Donald John Trump (June 14, 1946 – September 21, 2026)
        was an American politician.</p>
        """
        detected, reasons, _lead = watch.detect_death_notice(html)
        self.assertTrue(detected)
        self.assertEqual(len(reasons), 2)
        self.assertIn("Died:", reasons[0])

    def test_past_tense_without_death_range_is_not_detected(self) -> None:
        html = """
        <p>Donald John Trump (born June 14, 1946) was the 45th president
        and is an American politician.</p>
        """
        detected, reasons, _lead = watch.detect_death_notice(html)
        self.assertFalse(detected)
        self.assertEqual(reasons, [])

    def test_blank_died_field_is_not_detected(self) -> None:
        html = """
        <table class="infobox">
          <tr><th class="infobox-label">Died</th><td> </td></tr>
        </table>
        <p>Donald John Trump (born June 14, 1946) is an American politician.</p>
        """
        detected, _reasons, _lead = watch.detect_death_notice(html)
        self.assertFalse(detected)

    def test_lead_detection_allows_name_without_middle_name(self) -> None:
        html = """
        <p>Donald Trump (1946–2026) was an American politician.</p>
        """
        detected, reasons, _lead = watch.detect_death_notice(html)
        self.assertTrue(detected)
        self.assertEqual(len(reasons), 1)


class RequestTests(unittest.TestCase):
    def test_retry_after_seconds(self) -> None:
        self.assertEqual(watch._retry_after({"Retry-After": "45"}), 45)

    def test_retry_after_http_date(self) -> None:
        retry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)
        value = email.utils.format_datetime(retry_at, usegmt=True)
        delay = watch._retry_after({"Retry-After": value})
        self.assertIsNotNone(delay)
        self.assertGreaterEqual(delay, 58)
        self.assertLessEqual(delay, 60)

    def test_invalid_retry_after(self) -> None:
        self.assertIsNone(watch._retry_after({"Retry-After": "not-a-date"}))


class StateTransitionTests(unittest.TestCase):
    def make_config(self, path: Path) -> watch.Config:
        return watch.Config(
            ntfy_topic="test-topic-with-enough-randomness",
            ntfy_server="https://ntfy.sh",
            ntfy_token=None,
            contact="operator@example.com",
            poll_seconds=20,
            state_file=path,
            timeout_seconds=5,
        )

    def test_alert_is_sent_once_until_notice_is_removed(self) -> None:
        living = "<p>Donald John Trump (born June 14, 1946) is an American politician.</p>"
        deceased = """
        <table><tr><th class="infobox-label">Died</th><td>September 21, 2026</td></tr></table>
        <p>Donald John Trump (June 14, 1946 – September 21, 2026) was an American politician.</p>
        """
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_config(Path(directory) / "state.json")
            state = {}
            with (
                patch.object(watch, "latest_revision", side_effect=[(1, "t1"), (2, "t2"), (3, "t3")]),
                patch.object(watch, "rendered_lead", side_effect=[deceased, deceased, living]),
                patch.object(watch, "wikidata_death_date", return_value="2026-09-21T00:00:00Z"),
                patch.object(watch, "publish_ntfy") as publish,
            ):
                state = watch.check_once(config, state)
                self.assertTrue(state["alert_active"])
                self.assertEqual(publish.call_count, 1)

                state = watch.check_once(config, state)
                self.assertTrue(state["alert_active"])
                self.assertEqual(publish.call_count, 1)

                state = watch.check_once(config, state)
                self.assertFalse(state["alert_active"])
                self.assertEqual(publish.call_count, 2)
                self.assertEqual(publish.call_args.kwargs["title"], "Wikipedia death notice removed")

            self.assertEqual(watch.load_state(config.state_file), state)

    def test_unchanged_revision_does_not_download_article(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_config(Path(directory) / "state.json")
            state = {"revision_id": 50, "alert_active": False}
            with (
                patch.object(watch, "latest_revision", return_value=(50, "t50")),
                patch.object(watch, "rendered_lead") as rendered_lead,
            ):
                result = watch.check_once(config, state)
            self.assertIs(result, state)
            rendered_lead.assert_not_called()

    def test_failed_notification_does_not_advance_state(self) -> None:
        deceased = """
        <table><tr><th class="infobox-label">Died</th><td>September 21, 2026</td></tr></table>
        """
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_config(Path(directory) / "state.json")
            with (
                patch.object(watch, "latest_revision", return_value=(10, "t10")),
                patch.object(watch, "rendered_lead", return_value=deceased),
                patch.object(watch, "wikidata_death_date", return_value=None),
                patch.object(watch, "publish_ntfy", side_effect=watch.RequestError("ntfy unavailable")),
            ):
                with self.assertRaises(watch.RequestError):
                    watch.check_once(config, {})
            self.assertFalse(config.state_file.exists())


if __name__ == "__main__":
    unittest.main()
