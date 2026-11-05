"""How a student reports a problem.

The report has to end up as a GitHub issue the student can read before
it is sent, and it has to keep the email address so that we can answer.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from praatao import feedback


class BodyTests(unittest.TestCase):
    def test_the_body_carries_the_feedback_and_the_email(self) -> None:
        body = feedback.build_body(
            "卡片讲错了对象", "student@example.com", praat_version="6.4.12"
        )
        self.assertIn("卡片讲错了对象", body)
        self.assertIn("student@example.com", body)
        self.assertIn("Praatao", body)
        self.assertIn("6.4.12", body)

    def test_the_body_is_shaped_for_a_program(self) -> None:
        body = feedback.build_body("x", "y@example.com")
        self.assertIn("<!-- praatao-feedback:begin -->", body)
        self.assertIn("<!-- praatao-feedback:end -->", body)
        self.assertIn("email: y@example.com", body)

    def test_no_email_is_still_a_valid_body(self) -> None:
        body = feedback.build_body("只有文字")
        self.assertIn("email: (none)", body)

    def test_the_title_uses_the_first_line(self) -> None:
        self.assertEqual(
            feedback.build_title("卡片不出现了\n第二行"), "[反馈] 卡片不出现了"
        )

    def test_a_very_long_title_is_cut(self) -> None:
        title = feedback.build_title("很长的标题" * 40)
        self.assertLessEqual(len(title), 90)


class UrlTests(unittest.TestCase):
    def test_the_url_points_at_the_new_issue_page(self) -> None:
        url = feedback.issue_url("[反馈] 测试", "正文\n第二行")
        parsed = urlparse(url)
        self.assertEqual(parsed.netloc, "github.com")
        self.assertEqual(
            parsed.path, f"/{feedback.GITHUB_OWNER}/{feedback.GITHUB_REPO}/issues/new"
        )
        query = parse_qs(parsed.query)
        self.assertEqual(query["title"][0], "[反馈] 测试")
        self.assertIn("第二行", query["body"][0])


class LocalCopyTests(unittest.TestCase):
    def test_the_report_is_kept_on_this_machine(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            old = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = folder
            try:
                path = feedback.save_locally("正文", "标题")
            finally:
                if old is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = old
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("正文", text)
            self.assertIn("标题", text)


class FeedbackWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from PySide6 import QtWidgets
        except Exception:  # pragma: no cover - no Qt
            self.skipTest("PySide6 is not installed")
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_the_window_takes_the_text_and_the_email(self) -> None:
        from praatao.ui.qt.feedback import QtFeedbackWindow

        seen: list[tuple[str, str]] = []
        window = QtFeedbackWindow(
            None, lang="zh", on_submit=lambda text, mail: seen.append((text, mail))
        )
        self.addCleanup(window.destroy)
        window.text.setPlainText("卡片不见了")
        window.email.setText("student@example.com")
        window._submit()
        self.assertEqual(seen, [("卡片不见了", "student@example.com")])

    def test_an_empty_report_is_not_sent(self) -> None:
        from praatao.ui.qt.feedback import QtFeedbackWindow

        seen: list[tuple[str, str]] = []
        window = QtFeedbackWindow(
            None, lang="zh", on_submit=lambda text, mail: seen.append((text, mail))
        )
        self.addCleanup(window.destroy)
        window._submit()
        self.assertEqual(seen, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
