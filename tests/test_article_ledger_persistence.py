import json
import tempfile
import unittest
from pathlib import Path

from agents.article_ledger import (
    classify_candidates,
    load_article_state,
    make_record_from_article,
    save_article_state,
    known_source_identities,
)


class ArticleLedgerPersistenceTests(unittest.TestCase):
    def make_article(self, title, text, url):
        return {
            "title": title,
            "original_title": title,
            "text": text,
            "original_text": text,
            "source_url": url,
        }

    def test_load_state_merges_ledger_and_legacy_history_without_repeating_terminal_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            old_history = [
                self.make_article(
                    "Noticia publicada ayer",
                    "Esta noticia fue publicada correctamente y debe quedar bloqueada.",
                    "https://www.abcsaladillo.com.ar/general/publicada-ayer/",
                )
            ]
            old_history[0]["db_id"] = 10
            old_history[0]["db_status"] = "published"
            (data_dir / "scraped_articles.json").write_text(json.dumps(old_history), encoding="utf-8")

            ledger = {
                "https://www.abcsaladillo.com.ar/general/pendiente-hoy": {
                    "source_identity": "https://www.abcsaladillo.com.ar/general/pendiente-hoy",
                    "source_url": "https://www.abcsaladillo.com.ar/general/pendiente-hoy/",
                    "content_hash": "abc",
                    "allow_retry": True,
                }
            }
            (data_dir / "article_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")

            state = load_article_state(str(data_dir), now_iso="2026-11-02T15:00:00")

            self.assertIn("https://www.abcsaladillo.com.ar/general/publicada-ayer", state)
            self.assertIn("https://www.abcsaladillo.com.ar/general/pendiente-hoy", state)
            self.assertEqual([], known_source_identities([state["https://www.abcsaladillo.com.ar/general/pendiente-hoy"]]))
            self.assertEqual(["https://www.abcsaladillo.com.ar/general/publicada-ayer"], known_source_identities([state["https://www.abcsaladillo.com.ar/general/publicada-ayer"]]))

    def test_save_state_updates_status_and_db_id_after_processing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = self.make_article(
                "Nueva noticia",
                "Una nota local con texto suficiente para ser procesada por el pipeline.",
                "https://www.abcsaladillo.com.ar/general/nueva-noticia/",
            )
            _, _, results = classify_candidates([candidate], {}, [])
            state = {results[0]["source_identity"]: make_record_from_article(candidate)}

            save_article_state(
                tmpdir,
                state,
                processed_articles=[{**candidate, "id": 999}],
                duplicate_articles=[],
            )

            saved = json.loads((Path(tmpdir) / "article_ledger.json").read_text(encoding="utf-8"))
            record = saved["https://www.abcsaladillo.com.ar/general/nueva-noticia"]
            self.assertEqual("draft", record["status"])
            self.assertEqual(999, record["db_id"])


if __name__ == "__main__":
    unittest.main()
