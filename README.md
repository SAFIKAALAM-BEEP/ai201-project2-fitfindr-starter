# FitFindr

A secondhand shopping agent that takes a natural-language query, finds matching thrifted listings, suggests a complete outfit using the user's wardrobe, and generates a shareable social media caption.

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

**Run the Gradio UI:**
```bash
python app.py
```

**Run the CLI test:**
```bash
python agent.py
```

**Run tests:**
```bash
pytest tests/test_tools.py -v                  # all tests (requires GROQ_API_KEY)
pytest tests/test_tools.py -v -m "not llm"    # search_listings tests only (no API key needed)
```

---

## Project Structure

```
fitfindr/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe schema + example wardrobe
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── tools.py                   # Three agent tools
├── agent.py                   # Planning loop (run_agent)
├── app.py                     # Gradio interface
├── tests/
│   └── test_tools.py          # Pytest test suite
├── planning.md                # Spec and architecture
└── requirements.txt
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches the mock listings dataset for items matching the user's request and returns results sorted by relevance.

**Parameters:**

| Name | Type | Description |
|---|---|---|
| `description` | `str` | Free-text description of the item (e.g. `"vintage graphic tee"`). Matched against each listing's `title`, `description`, and `style_tags` fields. |
| `size` | `str \| None` | Size string to filter by (e.g. `"M"`, `"W30"`, `"S/M"`). Case-insensitive substring match against the listing's `size` field. Pass `None` to skip size filtering. |
| `max_price` | `float \| None` | Price ceiling in USD (inclusive). Pass `None` to skip price filtering. |

**Returns:** `list[dict]` — matching listing dicts sorted by keyword overlap score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches — never raises.

**Does not call the LLM.** Purely local filtering and scoring.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given the thrifted item and the user's wardrobe, generates a specific 2–4 sentence outfit suggestion using Groq's `llama-3.3-70b-versatile`.

**Parameters:**

| Name | Type | Description |
|---|---|---|
| `new_item` | `dict` | A listing dict from `search_listings` — the item being considered. Uses `title`, `colors`, `style_tags`, `category`, `condition`. |
| `wardrobe` | `dict` | Wardrobe object with an `"items"` key containing a list of wardrobe item dicts (each with `id`, `name`, `category`, `colors`, `style_tags`, optional `notes`). May be empty. |

**Returns:** `str` — a styling suggestion in second-person voice, naming specific wardrobe pieces by their `name` field. If `wardrobe["items"]` is empty, returns general styling advice instead of crashing.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Generates a 1–2 sentence Instagram/TikTok caption for the thrift find and outfit, in a casual Gen Z voice.

**Parameters:**

| Name | Type | Description |
|---|---|---|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit`. Used to pull specific wardrobe pieces to mention in the caption. |
| `new_item` | `dict` | The listing dict for the purchased item. Uses `title`, `price`, `platform`, `colors`. |

**Returns:** `str` — a lowercase, casual caption that mentions the platform, price, and one specific outfit piece. Uses LLM temperature 1.2 so output varies across runs. Returns a fallback error string (not an exception) if `outfit` is empty or whitespace-only.

---

## Planning Loop

`run_agent(query, wardrobe)` in `agent.py` executes these steps sequentially and returns a session dict:

**Step 1 — Parse.** `_parse_query()` uses regex to extract three things from the user's natural-language query: `description` (the item keywords, with price/size phrases stripped out), `size` (matched from "size M", "W30 L32", "US 8", "in XL" patterns), and `max_price` (matched from "under $30", "less than 40", "up to $25", etc.).

**Step 2 — Search.** Calls `search_listings(description, size, max_price)`. If the result list is empty, sets `session["error"]` to a specific, actionable message and returns early. `suggest_outfit` is never called on empty input.

**Step 3 — Select.** Sets `session["selected_item"] = results[0]` (the highest-relevance match).

**Step 4 — Suggest.** Calls `suggest_outfit(selected_item, wardrobe)`. If `wardrobe["items"]` is empty, sets `session["wardrobe_empty"] = True` before calling (the tool handles it gracefully). If the LLM returns an empty string (unexpected failure), sets `session["error"]` and returns early.

**Step 5 — Fit card.** Calls `create_fit_card(outfit_suggestion, selected_item)`. This step never causes early exit — if the outfit string is missing the tool returns a fallback caption string.

**Step 6 — Return.** Returns the completed session dict.

The key property of the loop: it branches on the output of each tool. Different queries produce different selected items, different outfit suggestions, and different captions. The no-results path halts after step 2 and sets `session["fit_card"] = None` — `suggest_outfit` is not called.

---

## State Management

All state for one interaction lives in a single `session` dict, initialized fresh by `_new_session()` at the start of each call to `run_agent()`. State is never shared across interactions.

| Key | Type | Set by | Read by |
|---|---|---|---|
| `query` | `str` | `_new_session` | — (reference only) |
| `parsed` | `dict` | `_parse_query` | `search_listings` call |
| `search_results` | `list[dict]` | `search_listings` | Loop (empty check), display |
| `selected_item` | `dict \| None` | Loop (step 3) | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | `dict` | `_new_session` | `suggest_outfit` |
| `wardrobe_empty` | `bool` | Loop (step 4) | `handle_query` (adds UI note) |
| `outfit_suggestion` | `str \| None` | `suggest_outfit` | `create_fit_card`, final response |
| `fit_card` | `str \| None` | `create_fit_card` | Final response |
| `error` | `str \| None` | Loop (on failure) | `handle_query` (early exit check) |

Data flows forward only — no tool reads a key set by a later tool. `selected_item` is the central handoff: it flows from `search_listings` output → `suggest_outfit` input → `create_fit_card` input. I verified this with an identity check (`session["selected_item"] is session["search_results"][0]`) to confirm no copying or re-fetching happens between steps.

---

## Error Handling

### `search_listings` — no results

**Condition:** The filtered and scored listing list is empty (no keyword overlap after price/size filtering, or the filters alone eliminate everything).

**Agent response:** Sets `session["error"]` to a specific message that names the query, size, and price used, then suggests concrete next steps. `selected_item`, `outfit_suggestion`, and `fit_card` all remain `None`. The loop returns immediately — `suggest_outfit` is not called.

**Example from testing:**

Query: `"designer ballgown size XXS under $5"`

```
session["error"] = "No listings matched 'designer ballgown' in size XXS under $5.
Try broadening your search — remove the size filter, raise your price limit, or
use a more general term (e.g. 'graphic tee' instead of 'band tee')."

session["selected_item"]    → None
session["outfit_suggestion"] → None
session["fit_card"]          → None
```

The Gradio UI displays this error in the first output panel and leaves the other two blank.

---

### `suggest_outfit` — empty wardrobe

**Condition:** `wardrobe["items"]` is an empty list (new user with no wardrobe entered).

**Agent response:** `suggest_outfit` detects the empty wardrobe before building the LLM prompt and switches to a general styling prompt — asking for advice on what kinds of bottoms, shoes, and accessories pair well with the item, based solely on its style tags and colors. It returns a non-empty string. The loop continues normally to `create_fit_card`. `handle_query` appends a note to the outfit panel: *"You haven't added any wardrobe items yet, so this is a general styling suggestion."*

**Example from testing:**

```python
results = search_listings("vintage graphic tee", size=None, max_price=50)
suggest_outfit(results[0], get_empty_wardrobe())
# → "This vintage piece pairs beautifully with high-waisted wide-leg trousers
#    and chunky platform sneakers. Layer a cropped zip hoodie over the top for
#    a relaxed streetwear look, and finish with a minimal crossbody bag."
# No exception raised. Non-empty string returned.
```

---

### `create_fit_card` — empty outfit string

**Condition:** `outfit` argument is an empty string or whitespace only (would happen if `suggest_outfit` returned an empty string and the LLM failure guard in the loop somehow didn't catch it, or in direct unit testing).

**Agent response:** The function returns the fallback string `"couldn't generate a fit card — outfit suggestion was missing 🤷"` immediately, before making any LLM call. No exception is raised. This step never causes early exit — the loop always completes.

**Example from testing:**

```python
results = search_listings("vintage graphic tee", size=None, max_price=50)
create_fit_card("", results[0])
# → "couldn't generate a fit card — outfit suggestion was missing 🤷"
# No exception raised.
```

---

## Spec Reflection

**What matched the spec:** The three-tool sequence, the session dict structure, the early-exit on empty `search_listings` results, and the `selected_item = results[0]` selection step all worked exactly as designed in `planning.md`. The state management table in the spec translated directly into code — each key maps to a single write site and one or more read sites, and nothing is re-fetched.

**What I changed from the spec:** The query parser turned out to need more care than the spec described. The initial regex for "size M" greedily captured the following word — so "size XXS under $5" was parsed as size "XXS under", which corrupted the no-results error message to say "under under $5". The fix was restricting the optional second word in the size pattern to only match `L`-followed-by-digits (e.g. "W30 L32"), not arbitrary words. This wasn't in the spec because the problem only appeared during actual testing.

The `create_fit_card` LLM temperature was also higher than typical (1.2 vs. the more common 0.7) specifically to make captions vary across repeated runs on the same input — verified by calling the function three times and asserting the results aren't all identical.

---

## AI Tool Usage

### Instance 1 — Implementing `search_listings`

**Input to AI:** The Tool 1 spec block from `planning.md` (what it does, all three parameter definitions, the return value field list, and the empty-result failure mode), plus the first five listings from `listings.json` as example data. I also specified to use `load_listings()` from `utils/data_loader.py` rather than re-reading the file.

**What it produced:** A working implementation that filtered by price and size and scored by keyword overlap. The generated code returned the full listing dicts sorted by score, which matched the spec.

**What I changed:** The generated stop-word list was too aggressive and was filtering out useful search terms like "tee" and "90s". I replaced it with a smaller, more conservative list that only skips true function words (articles, prepositions, pronouns) and a few FitFindr-specific filler words like "looking" and "find". I also tightened the keyword stripping: the original used `.strip()` without removing punctuation from word edges, so queries with trailing commas would fail to match. I added `.strip(".,!?'\"()-")` per word.

---

### Instance 2 — Implementing the planning loop in `agent.py`

**Input to AI:** The full ASCII architecture diagram from `planning.md`'s `## Architecture` section, the Planning Loop section (all seven numbered steps with explicit conditional branches), and the State Management table. I shared all three together and asked it to implement `run_agent()` following the diagram's branch logic exactly.

**What it produced:** A correct sequential loop that initialized the session, parsed the query, called the three tools in order, and stored results in the session dict. The early-exit branch on empty `search_listings` results was present and correct.

**What I changed:** The generated `_parse_query` didn't strip the price and size phrases from the description — it extracted the values but left the original query string as the description. This meant `search_listings` was being called with descriptions like `"vintage tee under $30 size M"`, and "under", "$30", "size", and "M" were being scored as keywords against listing text, adding noise to relevance rankings. I added the regex substitution steps that remove each extracted phrase from the description before passing it to `search_listings`. I also added the `wardrobe_empty` flag, which the generated code omitted.