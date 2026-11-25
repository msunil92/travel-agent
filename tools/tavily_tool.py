"""Tavily-backed web research used for hotel and destination suggestions."""

import os
from functools import lru_cache

from tavily import TavilyClient
from dotenv import load_dotenv


load_dotenv()


@lru_cache(maxsize=1)
def _get_client() -> TavilyClient:
    """Create and reuse the Tavily client when web research is first requested.

    The API key is loaded lazily so importing the application does not require
    Tavily credentials before any search is attempted.

    Raises:
        ValueError: If ``TRAVILY_API_KEY`` is not configured.
    """
    api_key = os.getenv("TRAVILY_API_KEY")
    if not api_key:
        raise ValueError("TRAVILY_API_KEY is missing. Please add it to your .env file.")
    return TavilyClient(api_key=api_key)


def tavily_search(query: str) -> str:
    """Search the web and format a compact set of source-backed results.

    Each result includes its title, URL, and a content excerpt capped at roughly
    300 characters to keep downstream model prompts concise.

    Args:
        query: Non-empty search phrase.

    Returns:
        Numbered search results separated by blank lines, or an empty string
        when Tavily returns no results.

    Raises:
        ValueError: If the query is blank or the Tavily API key is missing.
    """
    query = query.strip()
    if not query:
        raise ValueError("Search query must not be empty.")

    response = _get_client().search(
        query=query,
        max_results=5,
    )

    results = []
    for i, r in enumerate(response["results"], 1):
        title = str(r.get("title") or "NA")
        url = str(r.get("url") or "")
        content = str(r.get("content") or "").strip()

        if len(content) > 300:
            content = content[:300].rsplit(" ", 1)[0] + "..."

        results.append(f"{i}. **{title}**\n {url}\n {content}")

    return "\n\n".join(results)

