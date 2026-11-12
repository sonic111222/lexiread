import io
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from backend.ai import AIError


def _upload():
    buffer = io.BytesIO()
    Image.new("RGB", (12, 12), "white").save(buffer, "PNG")
    buffer.seek(0)
    return {"image": (buffer, "question.png")}


class OcrApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_ai_vision_result_is_returned(self):
        with (
            patch("backend.api.stored_settings", return_value={"ocr": {"ai_vision": True}}),
            patch(
                "backend.api.ocr.save_upload",
                return_value=(Path("question.png"), "/api/uploads/question.png", "question.png"),
            ),
            patch("backend.api.ai.is_configured", return_value=True),
            patch(
                "backend.api.ai.transcribe_image",
                return_value="Reading Comprehension\n\n1. What is the main idea?",
            ),
        ):
            response = self.client.post("/api/ocr", data=_upload())
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["meta"]["engine"], "AI 视觉识别")
        self.assertTrue(payload["data"]["meta"]["ai_vision"])

    def test_ai_failure_falls_back_to_local_ocr(self):
        local = {
            "text": "Reading Comprehension",
            "meta": {"engine": "Windows OCR", "language": "zh-Hans-CN", "warning": "缺少英文语言包"},
        }
        with (
            patch("backend.api.stored_settings", return_value={"ocr": {"ai_vision": True}}),
            patch(
                "backend.api.ocr.save_upload",
                return_value=(Path("question.png"), "/api/uploads/question.png", "question.png"),
            ),
            patch("backend.api.ai.is_configured", return_value=True),
            patch("backend.api.ai.transcribe_image", side_effect=AIError("model does not support images")),
            patch("backend.api.ocr.recognize", return_value=local),
        ):
            response = self.client.post("/api/ocr", data=_upload())
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        meta = payload["data"]["meta"]
        self.assertFalse(meta["ai_vision"])
        self.assertIn("AI 视觉识别失败", meta["warning"])
        self.assertIn("缺少英文语言包", meta["warning"])


    def test_language_settings_endpoint_opens_windows_settings(self):
        with (
            patch("backend.api.os.name", "nt"),
            patch("backend.api.subprocess.Popen") as popen,
        ):
            response = self.client.post("/api/ocr/language-settings")
        self.assertTrue(response.get_json()["ok"])
        popen.assert_called_once()
        self.assertIn("ms-settings:regionlanguage", popen.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
