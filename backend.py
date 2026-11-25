"""LangGraph workflow for gathering travel data and composing trip plans."""

import operator
import os
import uuid
from functools import lru_cache
from typing import Annotated, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

load_dotenv()

from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    """Create and reuse the configured Groq chat model on first use.

    Deferring construction lets the web page and API start without requiring
    model credentials until a user actually requests a travel plan.

    Raises:
        ValueError: If ``GROQ_API_KEY`` is not configured.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key)


class TravelState(TypedDict):
    """Shared LangGraph state passed between travel-planning agents.

    ``messages`` accumulates conversational messages; the other fields hold the
    request, research results, generated itinerary, and workflow call count.
    """

    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int



# =========================
# Flight Agent
# =========================

def flight_agent(state: TravelState):
    """Fetch live flight-status information for the user's travel request.

    Args:
        state: Current graph state containing ``user_query``.

    Returns:
        The flight search text, a status message, and the updated call count.
    """
    query = state["user_query"]
    flight_data = search_flights(query)

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight results fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



# =========================
# Hotel Agent
# =========================

def hotel_agent(state: TravelState):
    """Search the web for hotel suggestions relevant to the requested trip.

    Args:
        state: Current graph state containing ``user_query``.

    Returns:
        The hotel research text, a status message, and the updated call count.
    """
    query = f"Best hotels for {state['user_query']}"
    hotel_results = tavily_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel information fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }





# =========================
# Itinerary Agent
# =========================

def itinerary_agent(state: TravelState):
    """Generate an English day-by-day itinerary from the collected research.

    The model is instructed to distinguish suggestions from verified facts and
    avoid inventing live availability, prices, or bookings.

    Args:
        state: Request, flight results, and hotel research from earlier nodes.

    Returns:
        The generated itinerary, its model message, and the updated call count.
    """
    prompt = f"""
Create a practical day-by-day travel itinerary based on the request and research.

User Query:
{state['user_query']}

Flight Results:
{state['flight_results']}

Hotel Results:
{state['hotel_results']}

Do not use tables. Use a "### Day N — Place" heading for each day, followed by
2–4 short bullet points. Keep the plan realistic for the requested trip length.
Do not invent confirmed bookings, prices, opening hours, or live availability;
label any unsourced activity as a suggestion. If the trip length or another
important detail is missing, state a reasonable assumption.
"""

    response = get_llm().invoke([
        SystemMessage(content="You are an expert travel planner. Respond in English, regardless of the language used in the request or research."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



# =========================
# Final Response Agent
# =========================

def final_agent(state: TravelState):
    """Compose the user-facing trip plan from the request and agent outputs.

    Args:
        state: Request, flight and hotel research, and generated itinerary.

    Returns:
        The final model message and the updated workflow call count.
    """
    final_prompt = f"""
Create a useful, easy-to-scan travel plan for the user. Write in English.

User Request:
{state['user_query']}

Flights:
{state['flight_results']}

Hotels:
{state['hotel_results']}

Itinerary:
{state['itinerary']}

Use these Markdown sections, in this order:
## Trip overview
## Flights
## Places to stay
## Day-by-day plan
## Budget notes
## Before you go

Do not use tables. For the day-by-day plan, use a "### Day N — Place" heading
for every day, followed by 2–4 short bullets. Use short paragraphs and bullets,
and avoid repeating the same information.
Base factual claims only on the request and the supplied research. Never invent
flight times, fares, hotel prices, availability, ratings, or booking confirmations.
Clearly say when live flight data or prices are unavailable. Treat hotel search
results as suggestions, not verified availability or endorsements. If a budget
cannot be calculated from the supplied information, say so instead of guessing.
"""

    response = get_llm().invoke([
        SystemMessage(content="You are a professional travel-planning assistant. Respond in English. Be clear, accurate, concise, and do not claim that anything has been booked."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Build Graph
# =========================

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


travel_graph = graph.compile()


# =========================
# Function for FastAPI
# =========================

def run_travel_agent(user_input: str, thread_id: Optional[str] = None):
    """Invoke the travel graph and return its final answer and research.

    A fresh thread identifier is generated when one is not supplied. The graph
    runs flight search, hotel research, itinerary generation, and final drafting
    in sequence.

    Args:
        user_input: The user's travel-planning question.
        thread_id: Optional identifier associated with this invocation.

    Returns:
        A dictionary containing the answer, thread ID, research fields, and
        workflow call count.
    """
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = travel_graph.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "llm_calls": 0
        },
        config=config
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }