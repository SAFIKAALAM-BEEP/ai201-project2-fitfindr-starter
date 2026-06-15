"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

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

# Common words that don't carry search signal — skipped during scoring
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "for", "in", "on", "at", "to",
    "i", "am", "is", "are", "was", "were", "it", "its", "me", "my",
    "im", "looking", "want", "need", "get", "find", "something",
    "with", "of", "up", "out", "some", "any", "this", "that",
}


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()

    # 1. Filter by price (inclusive ceiling)
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    # 2. Filter by size — case-insensitive substring match, ignore spaces
    if size is not None:
        size_needle = size.lower().replace(" ", "")
        listings = [
            l for l in listings
            if size_needle in l["size"].lower().replace(" ", "")
        ]

    # 3. Score each remaining listing by keyword overlap with description
    keywords = {
        word.lower().strip(".,!?'\"()-")
        for word in description.split()
        if len(word.strip(".,!?'\"()-")) > 2
        and word.lower().strip(".,!?'\"()-") not in _STOP_WORDS
    }

    scored = []
    for listing in listings:
        # Build one searchable text blob from the most signal-rich fields
        searchable = " ".join([
            listing["title"],
            listing["description"],
            " ".join(listing["style_tags"]),
            listing["category"],
        ]).lower()

        score = sum(1 for kw in keywords if kw in searchable)

        # 4. Drop listings with zero keyword overlap
        if score > 0:
            scored.append((score, listing))

    # 5. Sort by score descending, return just the listing dicts
    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest a complete outfit.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offers general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    item_summary = (
        f"Name: {new_item.get('title', 'Unknown item')}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Style: {', '.join(new_item.get('style_tags', []))}\n"
        f"Category: {new_item.get('category', 'unknown')}\n"
        f"Condition: {new_item.get('condition', 'unknown')}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        # Empty wardrobe: give general styling advice based on item's tags/colors
        prompt = (
            "You are a personal stylist. A user just thrifted this item:\n"
            f"{item_summary}\n\n"
            "They haven't shared their wardrobe yet. Give general styling advice: "
            "what kinds of bottoms, shoes, and accessories pair well with it, "
            "and what vibe or aesthetic it suits. "
            "2–4 sentences, second person voice (say 'you'/'your'), casual and specific. "
            "Output only the styling advice — no preamble."
        )
    else:
        wardrobe_text = "\n".join(
            f"- {item['name']} ({item['category']}; colors: {', '.join(item['colors'])})"
            + (f"; note: {item['notes']}" if item.get("notes") else "")
            for item in wardrobe_items
        )
        prompt = (
            "You are a personal stylist. A user just thrifted this item:\n"
            f"{item_summary}\n\n"
            f"Their wardrobe includes:\n{wardrobe_text}\n\n"
            "Suggest a specific outfit using the new item and named pieces from their wardrobe. "
            "Refer to wardrobe items by the exact name listed above. "
            "Include a bottom, shoes, and optionally one outerwear or accessory if it makes sense. "
            "2–4 sentences, second person voice (say 'you'/'your'), casual and specific. "
            "Output only the styling suggestion — no preamble."
        )

    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 1–2 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message
        string — does NOT raise an exception.
    """
    # Guard: empty or whitespace-only outfit
    if not outfit or not outfit.strip():
        return "couldn't generate a fit card — outfit suggestion was missing 🤷"

    title = new_item.get("title", "this thrift find")
    price = new_item.get("price")
    platform = new_item.get("platform", "a thrift app")
    colors = ", ".join(new_item.get("colors", []))

    price_str = f"${int(price)}" if price is not None else "a steal"

    prompt = (
        "You are a Gen Z fashion enthusiast writing an Instagram caption for a thrift find.\n\n"
        f"Item: {title}\n"
        f"Price: {price_str}\n"
        f"Platform: {platform}\n"
        f"Colors: {colors}\n"
        f"Outfit: {outfit}\n\n"
        "Write a 1–2 sentence caption that:\n"
        "- Is entirely lowercase, sounds like a real OOTD post — NOT a product description\n"
        "- Mentions where it was thrifted and the price naturally (once each)\n"
        "- References one specific piece from the outfit description above\n"
        "- Ends with exactly one emoji\n"
        "Output only the caption text, nothing else."
    )

    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.2,   # higher temp → captions vary across runs
        max_tokens=100,
    )
    return response.choices[0].message.content.strip()