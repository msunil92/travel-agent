"""Unit tests for Tavily query validation and result formatting."""

import unittest
from unittest.mock import patch

from tools import tavily_tool


class TavilyToolTests(unittest.TestCase):
    """Test web-search behavior using a mocked Tavily client."""

    @patch("tools.tavily_tool._get_client")
    def test_search_formats_and_truncates_results(self, get_client):
        """Search results include source details and bounded content excerpts."""
        long_content = "travel advice " * 40
        get_client.return_value.search.return_value = {
            "results": [
                {
                    "title": "Island guide",
                    "url": "https://example.test/guide",
                    "content": long_content,
                }
            ]
        }

        result = tavily_tool.tavily_search("  Sri Lanka hotels  ")

        self.assertIn("1. **Island guide**", result)
        self.assertIn("https://example.test/guide", result)
        self.assertTrue(result.endswith("..."))
        get_client.return_value.search.assert_called_once_with(
            query="Sri Lanka hotels",
            max_results=5,
        )

    @patch("tools.tavily_tool._get_client")
    def test_search_returns_empty_string_when_no_results(self, get_client):
        """An empty result set formats as an empty string."""
        get_client.return_value.search.return_value = {"results": []}

        self.assertEqual(tavily_tool.tavily_search("hotels"), "")

    @patch("tools.tavily_tool._get_client")
    def test_empty_query_is_rejected_without_search(self, get_client):
        """A whitespace-only query raises before constructing a search client."""
        with self.assertRaises(ValueError):
            tavily_tool.tavily_search("   ")

        get_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
