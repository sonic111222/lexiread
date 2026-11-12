import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PwaServiceTests(unittest.TestCase):
    def test_service_layer_works_without_flask(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            env = {
                "LEXIREAD_RESOURCE_DIR": str(ROOT),
                "LEXIREAD_BASE_DIR": str(ROOT),
                "LEXIREAD_BUNDLED_DATA_DIR": str(ROOT / "backend" / "data"),
                "LEXIREAD_DATA_DIR": str(data),
                "LEXIREAD_UPLOAD_DIR": str(data / "uploads"),
                "LEXIREAD_DB_PATH": str(data / "lexiread.db"),
                "PYTHONUTF8": "1",
            }
            snippet = f"""
import json, sys
sys.path.insert(0, {str(ROOT)!r})
from backend.samples import get_sample
import pwa_bridge.service as service
service.init()

boot = service.bootstrap()
sample_text = get_sample('reading')['text']
analysis = service.analyze(sample_text)
entry = service.word_lookup('deliberate')
from unittest.mock import patch
with patch.object(service.ai, 'is_configured', return_value=True), patch.object(service.ai, 'analyze', return_value={{'title_zh': '测试'}}):
    ai_result = service.ai_analyze(sample_text)

saved = service.wordbook_add('deliberate', entry)
items = service.wordbook_list()
csv_text = service.wordbook_export()
print(json.dumps({{
    'engine': boot['ocr']['engine'],
    'kind': analysis['kind'],
    'questions': len(analysis['questions']),
    'ai_shape': ai_result == {{'title_zh': '测试'}},
    'word': entry['word'],
    'saved': saved['item']['word'],
    'items': len(items['items']),
    'csv': 'deliberate' in csv_text,
}}, ensure_ascii=False))
"""
            result = subprocess.run(
                [sys.executable, "-c", snippet],
                cwd=str(ROOT),
                env={**os.environ, **env},
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(payload["engine"], "Tesseract.js")
            self.assertEqual(payload["kind"], "reading")
            self.assertEqual(payload["questions"], 4)
            self.assertTrue(payload["ai_shape"])
            self.assertEqual(payload["word"], "deliberate")
            self.assertEqual(payload["saved"], "deliberate")
            self.assertEqual(payload["items"], 1)
            self.assertTrue(payload["csv"])


if __name__ == "__main__":
    unittest.main()
