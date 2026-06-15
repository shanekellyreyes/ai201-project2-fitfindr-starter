"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Usage:
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from tools import search_listings, suggest_outfit, create_fit_card

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Use the LLM to extract description, size, and max_price from the query.
    Falls back to regex if the LLM call fails.

    Returns a dict with keys: description (str), size (str|None), max_price (float|None)
    """
    try:
        client = _get_groq_client()
        prompt = f"""Extract search parameters from this thrift shopping query.

Query: "{query}"

Reply with ONLY these three lines, exactly in this format:
description: <keywords describing the item, no size or price>
size: <size if mentioned, or null>
max_price: <maximum price as a number if mentioned, or null>

Examples:
description: vintage graphic tee
size: M
max_price: 30

description: 90s track jacket
size: null
max_price: null"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()

        parsed = {}
        for line in text.splitlines():
            if line.startswith("description:"):
                parsed["description"] = line.split(":", 1)[1].strip()
            elif line.startswith("size:"):
                val = line.split(":", 1)[1].strip()
                parsed["size"] = None if val.lower() == "null" else val
            elif line.startswith("max_price:"):
                val = line.split(":", 1)[1].strip()
                try:
                    parsed["max_price"] = None if val.lower() == "null" else float(val)
                except ValueError:
                    parsed["max_price"] = None

        # Fallback if any field missing
        if "description" not in parsed:
            parsed["description"] = query
        parsed.setdefault("size", None)
        parsed.setdefault("max_price", None)
        return parsed

    except Exception as e:
        print(f"[_parse_query] LLM parse failed, using fallback: {e}")
        # Regex fallback
        max_price = None
        price_match = re.search(r"\$?(\d+(?:\.\d+)?)", query)
        if price_match:
            max_price = float(price_match.group(1))

        size_match = re.search(
            r"\b(XXS|XS|S/M|S|M/L|M|L/XL|L|XL|XXL|W\d+|US\s?\d+)\b",
            query, re.IGNORECASE
        )
        size = size_match.group(1) if size_match else None

        # Strip price and size from description
        description = re.sub(r"\$?\d+(?:\.\d+)?", "", query)
        description = re.sub(
            r"\b(XXS|XS|S/M|S|M/L|M|L/XL|L|XL|XXL|W\d+|US\s?\d+)\b",
            "", description, flags=re.IGNORECASE
        )
        description = re.sub(r"\s+", " ", description).strip()

        return {"description": description, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop and returns
    the completed session dict.

    Args:
        query:    Natural language user request
        wardrobe: User's wardrobe dict

    Returns:
        Session dict. Check session["error"] first — if not None, the
        interaction ended early and outfit_suggestion/fit_card will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query
    try:
        parsed = _parse_query(query)
        session["parsed"] = parsed
    except Exception as e:
        session["error"] = f"Could not understand your query. Please try rephrasing it."
        return session

    description = parsed.get("description", query)
    size = parsed.get("size")
    max_price = parsed.get("max_price")

    # Step 3: Search listings
    try:
        results = search_listings(description, size=size, max_price=max_price)
        session["search_results"] = results
    except Exception as e:
        session["error"] = "Something went wrong while searching listings. Please try again."
        return session

    # Step 3 branch: no results → early exit
    if not results:
        session["error"] = (
            "No listings found for that search. "
            "Try broadening your description, adjusting the size, or raising the price limit."
        )
        return session

    # Step 4: Select top result
    session["selected_item"] = results[0]

    # Step 5: Suggest outfit
    try:
        outfit = suggest_outfit(session["selected_item"], wardrobe)
        session["outfit_suggestion"] = outfit
    except Exception as e:
        session["error"] = "Found a listing but couldn't generate outfit suggestions. Please try again."
        return session

    # Step 6: Create fit card
    try:
        fit_card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
        session["fit_card"] = fit_card
    except Exception as e:
        session["error"] = "Found a listing and outfit idea but couldn't generate the fit card. Please try again."
        return session

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
