"""Tests for deferred and cached model-client initialization."""

import os
import unittest
from unittest.mock import patch

import backend


class BackendTests(unittest.TestCase):
    """Verify model setup without making a network request to the provider."""

    def setUp(self):
        """Clear cached model state so each test starts independently."""
        backend.get_llm.cache_clear()

    def tearDown(self):
        """Prevent cached test clients from leaking into other tests."""
        backend.get_llm.cache_clear()

    def test_language_model_key_is_checked_when_client_is_requested(self):
        """The missing-key error is raised only when a model is requested."""
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "GROQ_API_KEY is missing"):
                backend.get_llm()

    def test_language_model_client_is_reused(self):
        """Repeated calls reuse the same configured Groq client instance."""
        client = object()
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
            with patch.object(backend, "ChatGroq", return_value=client) as factory:
                self.assertIs(backend.get_llm(), client)
                self.assertIs(backend.get_llm(), client)

        factory.assert_called_once_with(
            model="openai/gpt-oss-120b",
            api_key="test-key",
        )


if __name__ == "__main__":
    unittest.main()
