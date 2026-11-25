"""API-level tests for request validation and static page delivery."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app


class TravelAppTests(unittest.TestCase):
    """Exercise the FastAPI routes without invoking external travel services."""

    def setUp(self):
        """Create an isolated HTTP test client for each test."""
        self.client = TestClient(app)

    def test_home_and_static_assets_are_served(self):
        """The homepage and its stylesheet should be available to browsers."""
        page = self.client.get("/")
        stylesheet = self.client.get("/static/style.css")

        self.assertEqual(page.status_code, 200)
        self.assertIn("Waypoint", page.text)
        self.assertEqual(stylesheet.status_code, 200)

    @patch("app.run_travel_agent")
    def test_question_returns_agent_response(self, run_agent):
        """Valid questions are trimmed and passed to the travel agent."""
        run_agent.return_value = {
            "thread_id": "test-thread",
            "answer": "## Trip overview\nA sample plan.",
            "flight_results": "Flights",
            "hotel_results": "Hotels",
            "itinerary": "Itinerary",
            "llm_calls": 2,
        }

        response = self.client.post(
            "/api/ask",
            json={"question": "  Plan a trip to Sri Lanka  "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "## Trip overview\nA sample plan.")
        run_agent.assert_called_once_with("Plan a trip to Sri Lanka")

    def test_invalid_questions_are_rejected(self):
        """Blank, short, and oversized questions should fail validation."""
        for question in ("", "  ", "x", "x" * 2001):
            with self.subTest(question=question[:10]):
                response = self.client.post("/api/ask", json={"question": question})
                self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
