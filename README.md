# Waypoint

Waypoint is a small AI-assisted trip planner. Describe a trip in the web page
to receive a travel overview, flight information when available, hotel research,
and a day-by-day itinerary.

## Project structure

```text
.
├── app.py                  # FastAPI routes and request validation
├── backend.py              # LangGraph travel-planning workflow
├── tools/
│   ├── flight_tool.py      # AviationStack search and airport resolution
│   └── tavily_tool.py      # Hotel and destination web research
├── static/
│   ├── index.html          # Responsive planner page
│   ├── app.js              # Form handling and response rendering
│   └── style.css           # Responsive dark glass UI
├── tests/                  # Unit and API tests (external calls are mocked)
├── .env.example            # Environment variable template
└── requirements.txt
```

## Requirements

- Python 3.9 or later
- API keys for Groq and Tavily to generate travel plans
- An AviationStack API key for live flight status results (optional)

Flight status data is not ticket pricing. Hotel results and generated plans are
suggestions; confirm current availability, prices, and travel requirements with
the provider before booking.

## Setup

From the project directory, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On Windows PowerShell, activate it with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Create a local environment file and add your API keys:

```bash
cp .env.example .env
```

Set `GROQ_API_KEY` and `TRAVILY_API_KEY` in `.env`. Set
`AVIATIONSTACK_API_KEY` if live flight status is desired. `.env` is ignored by
Git; do not commit real API keys.

## Run the application

With the virtual environment active:

```bash
uvicorn app:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser. The interactive
API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

The planner endpoint accepts a JSON request:

```bash
curl -X POST http://127.0.0.1:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Plan a 5-day Sri Lanka trip from Bengaluru"}'
```

## Run tests

Tests use Python's built-in `unittest` runner and mock external API calls, so
they do not require working API keys or make network requests:

```bash
python -m unittest discover -s tests -v
```

The suite covers route and airport resolution, flight-result formatting and
error handling, Tavily result formatting, request validation, and the web/API
routes.
