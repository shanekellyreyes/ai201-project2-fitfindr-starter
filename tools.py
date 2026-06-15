"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
from dotenv import load_dotenv
from groq import Groq
from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for.
        size:        Size string to filter by, or None to skip size filtering.
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    try:
        listings = load_listings()
    except Exception as e:
        print(f"[search_listings] Failed to load listings: {e}")
        return []

    # Step 1: Filter by max_price
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    # Step 2: Filter by size (case-insensitive partial match)
    if size is not None:
        size_lower = size.lower()
        listings = [
            l for l in listings
            if size_lower in l["size"].lower()
        ]

    # Step 3: Score by keyword overlap with description
    keywords = [w.lower() for w in description.split()]

    def score(listing):
        searchable = " ".join([
            listing["title"],
            listing["description"],
            listing["category"],
            " ".join(listing["style_tags"]),
            " ".join(listing["colors"]),
            listing["brand"] or "",
        ]).lower()
        return sum(1 for kw in keywords if kw in searchable)

    # Step 4: Drop listings with score 0
    scored = [(l, score(l)) for l in listings]
    scored = [(l, s) for l, s in scored if s > 0]

    # Step 5: Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    return [l for l, _ in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict for the item the user is considering.
        wardrobe: A wardrobe dict with an 'items' key. May be empty.

    Returns:
        A non-empty string with outfit suggestions.
        If wardrobe is empty, returns general styling advice instead.
    """
    try:
        client = _get_groq_client()
        items = wardrobe.get("items", [])

        if not items:
            # Empty wardrobe — give general styling advice
            prompt = f"""You are a thrift fashion stylist.

A user just found this secondhand item:
- Name: {new_item['title']}
- Category: {new_item['category']}
- Style tags: {', '.join(new_item['style_tags'])}
- Colors: {', '.join(new_item['colors'])}
- Description: {new_item['description']}

They haven't told you what's in their wardrobe. Give them 1–2 general outfit ideas —
what kinds of pieces pair well with this item, what vibe it suits, and how to wear it.
Be specific and conversational, not generic."""

        else:
            # Build wardrobe summary
            wardrobe_lines = "\n".join(
                f"- {item['name']} ({item['category']}, {', '.join(item['colors'])})"
                for item in items
            )
            prompt = f"""You are a thrift fashion stylist.

A user just found this secondhand item:
- Name: {new_item['title']}
- Category: {new_item['category']}
- Style tags: {', '.join(new_item['style_tags'])}
- Colors: {', '.join(new_item['colors'])}
- Description: {new_item['description']}

Here's what's already in their wardrobe:
{wardrobe_lines}

Suggest 1–2 specific outfit combinations using the new item and named pieces
from their wardrobe. Be specific about which pieces to combine and why it works.
Keep it conversational and fashion-forward."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[suggest_outfit] Error: {e}")
        return (
            "Could not generate outfit suggestions. "
            "Try pairing this piece with simple basics like jeans and a white tee."
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty, returns a descriptive error message string.
    """
    # Guard against empty outfit
    if not outfit or not outfit.strip():
        return "Could not generate a fit card — outfit description was missing."

    try:
        client = _get_groq_client()

        prompt = f"""You are writing a casual Instagram/TikTok caption for a thrift outfit post.

The thrifted item:
- Name: {new_item['title']}
- Price: ${new_item['price']}
- Platform: {new_item['platform']}
- Style: {', '.join(new_item['style_tags'])}

The outfit idea:
{outfit}

Write a 2–4 sentence caption that:
- Sounds like a real person posting their OOTD (casual, authentic, not like an ad)
- Mentions the item name, price, and platform naturally — once each
- Captures the vibe of the outfit in specific terms
- Feels fun and shareable

Do not use hashtags. Do not use quotation marks around the caption."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.9,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[create_fit_card] Error: {e}")
        return "Fit card unavailable. Try again."
