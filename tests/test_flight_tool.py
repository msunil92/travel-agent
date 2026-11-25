"""Unit tests for airport resolution and AviationStack result handling."""

import unittest
from unittest.mock import patch

from tools import flight_tool


class FakeResponse:
    """Minimal response double exposing the JSON interface used by requests."""

    def __init__(self, data):
        """Store a payload that ``json`` will return to the flight tool."""
        self.data = data

    def json(self):
        """Return the configured API payload without performing network I/O."""
        return self.data


class FlightToolTests(unittest.TestCase):
    """Cover route parsing and flight API behavior with deterministic fixtures."""

    def test_clean_text_removes_punctuation_and_stop_words(self):
        """Location normalization removes query filler and punctuation."""
        self.assertEqual(
            flight_tool.clean_text("Plan a 7-day Japan trip under $2,000"),
            "a 7 japan 2 000",
        )

    def test_location_resolution_uses_iata_and_preferred_airports(self):
        """Known IATA codes, city preferences, and country preferences resolve."""
        self.assertEqual(flight_tool.resolve_location_to_iata("BLR"), "BLR")
        self.assertEqual(flight_tool.resolve_location_to_iata("Bengaluru"), "BLR")
        self.assertEqual(flight_tool.resolve_location_to_iata("Japan"), "NRT")

    def test_parse_route_handles_city_route_and_global_search(self):
        """Route parsing supports named endpoints and unfiltered global search."""
        self.assertEqual(
            flight_tool.parse_route("Flights from Bengaluru to Colombo"),
            ("BLR", "CMB"),
        )
        self.assertEqual(
            flight_tool.parse_route("Show worldwide flights"),
            (None, None),
        )

    def test_format_flight_handles_missing_nested_fields(self):
        """Partial API records are formatted with readable fallback values."""
        formatted = flight_tool.format_flight(
            {
                "airline": None,
                "flight": None,
                "departure": None,
                "arrival": None,
            }
        )

        self.assertIn("Airline: Unknown airline", formatted)
        self.assertIn("Flight: Unknown flight number", formatted)
        self.assertIn("Unknown departure airport", formatted)

    def test_search_rejects_non_positive_limits(self):
        """Invalid result limits fail before any provider request is made."""
        for limit in (0, -1, True):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    flight_tool.search_flights("BLR to CMB", limit=limit)

    def test_search_reports_missing_api_key_without_requesting(self):
        """Missing credentials produce an explanatory message without I/O."""
        with patch.object(flight_tool, "API_KEY", None):
            with patch.object(flight_tool.requests, "get") as get:
                result = flight_tool.search_flights("BLR to CMB")

        self.assertIn("AVIATIONSTACK_API_KEY is missing", result)
        get.assert_not_called()

    def test_search_formats_mocked_flight_results(self):
        """A mocked successful response is filtered and rendered as flight text."""
        payload = {
            "data": [
                {
                    "airline": {"name": "Example Air"},
                    "flight": {"iata": "EA123"},
                    "flight_status": "active",
                    "departure": {"airport": "Bengaluru", "iata": "BLR"},
                    "arrival": {"airport": "Colombo", "iata": "CMB"},
                }
            ]
        }

        with patch.object(flight_tool, "API_KEY", "test-key"):
            with patch.object(
                flight_tool.requests,
                "get",
                return_value=FakeResponse(payload),
            ) as get:
                result = flight_tool.search_flights("BLR to CMB", limit=1)

        self.assertIn("Live flights from BLR to CMB", result)
        self.assertIn("Example Air", result)
        self.assertIn("EA123", result)
        self.assertEqual(get.call_args.kwargs["params"]["limit"], 1)
        self.assertEqual(get.call_args.kwargs["params"]["dep_iata"], "BLR")
        self.assertEqual(get.call_args.kwargs["params"]["arr_iata"], "CMB")

    def test_search_handles_invalid_api_data(self):
        """Unexpected flight-data shapes return a clear provider-data message."""
        with patch.object(flight_tool, "API_KEY", "test-key"):
            with patch.object(
                flight_tool.requests,
                "get",
                return_value=FakeResponse({"data": {"unexpected": "shape"}}),
            ):
                result = flight_tool.search_flights("BLR to CMB")

        self.assertEqual(result, "Flight API returned invalid flight data.")


if __name__ == "__main__":
    unittest.main()
