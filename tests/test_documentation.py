import importlib.util
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_docs", ROOT / "scripts" / "check_docs.py")
DOC_CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOC_CHECKER)


class DocumentationTests(unittest.TestCase):
    def test_project_documents_and_navigation(self):
        self.assertEqual(DOC_CHECKER.check_docs(ROOT), 0)

    def test_broken_relative_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            for name in ("README.md", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md"):
                (root / name).write_text("# Example\n", encoding="utf-8")
            (root / "docs" / "index.md").write_text("[missing](missing.md)\n", encoding="utf-8")
            (root / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n", encoding="utf-8")
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(DOC_CHECKER.check_docs(root), 1)
            self.assertIn("Broken link", errors.getvalue())

    def test_schema_matches_event_contract(self):
        schema = json.loads((ROOT / "schemas" / "keyword-event.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(schema["properties"]["type"]["const"], "keyword_detected")
        self.assertEqual(set(schema["required"]), set(schema["properties"]))


if __name__ == "__main__":
    unittest.main()
