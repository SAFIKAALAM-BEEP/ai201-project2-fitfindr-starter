"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "wardrobe_empty": False,     # True when wardrobe["items"] was []
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex — no LLM call needed for this step.

    Returns:
        dict with keys: description (str), size (str | None), max_price (float | None)
    """
    q = query.strip()

    # --- Extract max_price ---
    # Matches: "under $30", "less than 40", "up to $25", "max $50", "budget $20"
    price_match = re.search(
        r'(?:under|less\s+than|up\s+to|max(?:imum)?|budget)\s*\$?\s*(\d+(?:\.\d+)?)'
        r'|\$\s*(\d+(?:\.\d+)?)\s*(?:or\s+less|max|maximum)',
        q, re.IGNORECASE
    )
    max_price = None
    if price_match:
        raw = price_match.group(1) or price_match.group(2)
        max_price = float(raw)

    # --- Extract size ---
    # "size M" phrase → W30/W30L32 waist codes → US shoe sizes → standalone code in context
    # Note: optional second word in "size X Y" is restricted to L-number (e.g. L32)
    # to avoid greedily capturing words like "under".
    size_match = re.search(
        r'\bsize[:\s]+([A-Za-z0-9/]+(?:\s+[Ll]\d{2})?)'       # "size M", "size S/M", "size W30 L32"
        r'|\b(W\d{2}(?:\s*[Ll]\d{2})?)\b'                     # "W30", "W30 L32"
        r'|\b(US\s*\d+(?:\.\d+)?)\b'                          # "US 8", "US8.5"
        r'|\bin\s+(XXS|XS|S/M|M/L|L/XL|XS|S|M|L|XL|XXL)\b', # "in M", "in XL"
        q, re.IGNORECASE
    )
    size = None
    if size_match:
        size = next(g for g in size_match.groups() if g is not None).strip()

    # --- Clean description ---
    # Remove the price phrase and size phrase so only item keywords remain.
    description = q
    if price_match:
        description = description[:price_match.start()] + " " + description[price_match.end():]
    description = re.sub(
        r'\bsize[:\s]+[A-Za-z0-9/]+(?:\s+[Ll]\d{2})?', '', description, flags=re.IGNORECASE
    )
    description = re.sub(r'\bW\d{2}(?:\s*[Ll]\d{2})?\b', '', description, flags=re.IGNORECASE)
    description = re.sub(r'\bUS\s*\d+(?:\.\d+)?\b', '', description, flags=re.IGNORECASE)
    description = re.sub(
        r'\bin\s+(XXS|XS|S/M|M/L|L/XL|XS|S|M|L|XL|XXL)\b', '', description, flags=re.IGNORECASE
    )
    # Collapse extra whitespace and strip stray punctuation
    description = re.sub(r'\s+', ' ', description).strip().strip(',.').strip()

    return {
        "description": description if description else q,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse query -> description, size, max_price
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Search listings
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    # Early exit: no results found
    if not results:
        desc = parsed["description"]
        size_clause = f" in size {parsed['size']}" if parsed["size"] else ""
        price_clause = f" under ${parsed['max_price']:.0f}" if parsed["max_price"] else ""
        session["error"] = (
            f"No listings matched '{desc}'{size_clause}{price_clause}. "
            "Try broadening your search — remove the size filter, raise your "
            "price limit, or use a more general term (e.g. 'graphic tee' instead "
            "of 'band tee')."
        )
        return session

    # Step 4: Select top result
    session["selected_item"] = results[0]

    # Step 5: Suggest outfit
    # Flag empty wardrobe before calling — suggest_outfit handles it gracefully
    if not wardrobe.get("items"):
        session["wardrobe_empty"] = True

    outfit = suggest_outfit(session["selected_item"], session["wardrobe"])

    # Unexpected LLM failure guard
    if not outfit or not outfit.strip():
        item = session["selected_item"]
        session["error"] = (
            f"Found a great listing ({item['title']}, "
            f"${item['price']:.0f} on {item['platform']}) but couldn't generate "
            "a styling suggestion right now. Try again in a moment."
        )
        return session

    session["outfit_suggestion"] = outfit

    # Step 6: Create fit card (never halts — fallback caption on failure)
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], session["selected_item"])

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