import unittest
from unittest.mock import Mock, patch

from agents.storage_agent import StorageAgent


class StorageAgentRecentArticlesTests(unittest.TestCase):
    def test_find_recent_processed_articles_queries_status_and_maps_db_id(self):
        agent = StorageAgent(table="articles")
        response = Mock(status_code=200)
        response.json.return_value = [
            {
                "id": 553,
                "title": "Nota publicada",
                "text": "Texto publicado",
                "slug": "nota-publicada",
                "status": "published",
                "is_published": True,
                "created_at": "2026-11-01T15:30:57.719793+00:00",
                "updatedAt": "2026-11-01T15:33:15.141000+00:00",
            }
        ]

        with patch("agents.storage_agent.requests.get", return_value=response) as get_mock:
            rows = agent.find_recent_processed_articles(days=3, limit=10)

        get_mock.assert_called_once()
        params = get_mock.call_args.kwargs["params"]
        self.assertEqual("id,title,text,slug,status,is_published,created_at,updatedAt", params["select"])
        self.assertEqual("created_at.desc", params["order"])
        self.assertEqual(10, params["limit"])
        self.assertIn("created_at", params)
        self.assertEqual(553, rows[0]["db_id"])

    def test_find_recent_processed_articles_returns_empty_on_http_error(self):
        agent = StorageAgent(table="articles")
        response = Mock(status_code=500)
        response.text = "boom"

        with patch("agents.storage_agent.requests.get", return_value=response):
            rows = agent.find_recent_processed_articles(days=3, limit=10)

        self.assertEqual([], rows)


if __name__ == "__main__":
    unittest.main()
