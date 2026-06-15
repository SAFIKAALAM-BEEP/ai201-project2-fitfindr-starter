# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Loads all listings from `data/listings.json` using `load_listings()` and filters them to return only entries that match the user's query, size, and price constraints. Results are sorted by relevance (title/description/style_tag match quality) so the best match appears first.

**Input parameters:**
- `description` (str): Free-text description of the item the user wants (e.g. "vintage graphic tee"). Matched against each listing's `title`, `description`, and `style_tags` fields using case-insensitive substring or keyword overlap.
- `size` (str | None): The user's size, e.g. `"M"`, `"W30"`, `"S/M"`. If provided, only listings whose `size` field contains this string (case-insensitive) are returned. If `None`, size filtering is skipped.
- `max_price` (float | None): Upper bound on price in USD. If provided, only listings where `price <= max_price` are returned. If `None`, price filtering is skipped.

**What it returns:**
A list of listing dicts, each containing: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str — one of "excellent", "good", "fair"), `price` (float), `colors` (list[str]), `brand` (str | None), `platform` (str — e.g. "depop", "poshmark", "thredUp"). The list is sorted so the highest-relevance match is at index 0. Returns an empty list `[]` if no listings pass all filters.

**What happens if it fails or returns nothing:**
If the returned list is empty, the agent does NOT proceed to `suggest_outfit`. Instead it immediately responds to the user: *"No listings matched '[query]'[in size X][under $Y]. Try broadening your search — remove the size filter, raise your price limit, or use a more general term like 'graphic tee' instead of 'band tee'."* The session ends here.

---

### Tool 2: suggest_outfit

**What it does:**
Takes the newly found listing and the user's wardrobe and generates a specific, actionable outfit suggestion by matching the new item's colors and style tags against wardrobe items by category (bottoms, outerwear, shoes, accessories). Returns a single natural-language styling paragraph.

**Input parameters:**
- `new_item` (dict): A single listing dict from `search_listings` results — the item the user is buying. Must include at minimum: `title`, `colors`, `style_tags`, `category`, `condition`, `price`, `platform`.
- `wardrobe` (dict): A wardrobe object in the schema defined in `data/wardrobe_schema.json`. Contains a key `"items"` whose value is a list of wardrobe item dicts, each with: `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`. May be an empty wardrobe (`{"items": []}`).

**What it returns:**
A single string — a 2–4 sentence styling suggestion written in second person (e.g. "Wear this with your wide-leg jeans and platform Docs..."). The suggestion names specific wardrobe items by their `name` field, describes how to style/tuck/layer the new item, and references one optional finishing piece (accessory or outerwear) from the wardrobe when available.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the agent skips wardrobe-referencing and instead returns a generic styling suggestion based solely on the new item's style tags and colors (e.g. "This tee pairs well with baggy dark denim, chunky sneakers, and a simple crossbody bag — a classic 90s streetwear formula."). The agent notes to the user: *"You haven't added any wardrobe items yet, so here's a general styling idea. Add your clothes to get a personalized suggestion."* The flow continues to `create_fit_card` using the generic suggestion.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, social-media-ready caption (1–2 sentences) in the voice of a thrift-obsessed Gen Z poster, referencing the specific item found and the outfit it's being worn with. Intended for sharing to Instagram stories, TikTok, or Depop profiles.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit` — used to pull specific wardrobe pieces to mention in the caption.
- `new_item` (dict): The listing dict for the purchased item — used for price, platform, and title details in the caption. Must contain at minimum: `title`, `price`, `platform`, `colors`.

**What it returns:**
A single string — a 1–2 sentence caption in lowercase, casual, first-person voice. It references how much the item cost, where it was thrifted from, and one specific wardrobe pairing from the outfit suggestion. May include one emoji at the end. Example: *"thrifted this faded bootleg tee off depop for $24 and it was literally made for my baggy jeans 🖤 vintage denim jacket doing the heavy lifting as always"*

**What happens if it fails or returns nothing:**
If `outfit` is an empty string or `new_item` is missing required fields (`price`, `platform`, `title`), the agent logs the incomplete input and returns a minimal fallback caption using only what's available: *"just thrifted something new and i'm obsessed 🖤"*. The agent still delivers this to the user rather than erroring out, since a fallback caption is more useful than nothing.

---

### Additional Tools (if any)

None required for the core flow. Potential stretch addition: `save_to_wardrobe(item, wardrobe)` — appends a purchased listing to the user's wardrobe file so future suggestions improve over time.

---

## Planning Loop

The planning loop runs once per user message. It executes steps sequentially — it never backtracks or re-runs a prior tool — and halts as soon as an early-exit condition is met.

**Step-by-step conditional logic:**

1. **Parse the user query.** Extract `description` (required), `size` (optional — look for "size M", "medium", "W30", etc.), and `max_price` (optional — look for "under $30", "less than 40", etc.) from the user's message.

2. **Call `search_listings(description, size, max_price)`.**
   - If `results` is `[]` (empty list): set `session["error"] = "no_results"`, compose the no-results message (see Tool 1 failure mode), return it to the user, and **stop**. Do not call any further tools.
   - If `results` is non-empty: set `session["selected_item"] = results[0]` and continue.

3. **Call `suggest_outfit(selected_item=session["selected_item"], wardrobe=session["wardrobe"])`.**
   - If `session["wardrobe"]["items"]` is empty before calling: set `session["wardrobe_empty"] = True`. Call `suggest_outfit` anyway — the tool handles this gracefully and returns a generic suggestion.
   - Set `session["outfit_suggestion"] = <return value>`.
   - If the return value is an empty string (unexpected tool failure): set `session["error"] = "suggest_failed"`, tell the user *"I found a great listing but couldn't generate a styling suggestion right now. Here's the item: [selected_item title, price, platform]."* and **stop**.

4. **Call `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.**
   - Set `session["fit_card"] = <return value>`.
   - If the return value is empty: use the fallback caption (see Tool 3 failure mode). Never stop here — always deliver something.

5. **Compose and return final response.** Include: the number of matches found, the selected listing's title/price/platform/condition/size, the outfit suggestion, and the fit card caption. If `session["wardrobe_empty"]` is True, append the wardrobe prompt note.

---

## State Management

The agent maintains a `session` dict for the duration of one user interaction. It is initialized fresh at the start of each query and is not persisted across conversations.

| Key | Type | Set by | Used by |
|-----|------|--------|---------|
| `session["query"]` | str | Parser (step 1) | `search_listings` input |
| `session["size"]` | str \| None | Parser (step 1) | `search_listings` input |
| `session["max_price"]` | float \| None | Parser (step 1) | `search_listings` input |
| `session["results"]` | list[dict] | `search_listings` | Loop (to check empty), display |
| `session["selected_item"]` | dict | Loop after search | `suggest_outfit`, `create_fit_card` |
| `session["wardrobe"]` | dict | Loaded at start from `get_example_wardrobe()` | `suggest_outfit` |
| `session["wardrobe_empty"]` | bool | Loop (step 3) | Final response composer |
| `session["outfit_suggestion"]` | str | `suggest_outfit` | `create_fit_card`, final response |
| `session["fit_card"]` | str | `create_fit_card` | Final response |
| `session["error"]` | str \| None | Loop (on failure) | Final response (early exit) |

Data flows forward only — no tool reads from a key set by a later tool. `selected_item` is the central handoff: it goes from `search_listings` output → `suggest_outfit` input → `create_fit_card` input.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match the query | *"No listings matched '[description]'[in size X][under $Y]. Try broadening your search — remove the size filter, raise your price limit, or use a more general term like 'graphic tee' instead of 'band tee'."* Flow stops; `suggest_outfit` is not called. |
| `suggest_outfit` | Wardrobe is empty | The tool returns a generic style suggestion using only the new item's tags/colors. Agent appends: *"You haven't added any wardrobe items yet, so here's a general styling idea. Add your clothes to get a personalized suggestion."* Flow continues to `create_fit_card`. |
| `create_fit_card` | Outfit input is missing or incomplete | Agent uses fallback caption: *"just thrifted something new and i'm obsessed 🖤"* and delivers it to the user. Flow never halts at this step. |

---

## Architecture

```
User query (natural language)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PARSER                                                             │
│  Extract: description (str), size (str|None), max_price (float|None)│
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
                    Session initialized
                    session["wardrobe"] = get_example_wardrobe()
                    session["error"] = None
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PLANNING LOOP                                                       │
│                                                                      │
│  Step 1 ──► search_listings(description, size, max_price)            │
│                 │                                                    │
│                 ├── results == [] ──────────────────────────────────►│
│                 │         session["error"] = "no_results"            │
│                 │         Return: "No listings matched. Try..."      │
│                 │         ◄─────────────────────────── STOP ─────────┘
│                 │
│                 └── results = [item, ...] (non-empty)
│                         session["selected_item"] = results[0]
│                         session["results"] = results
│                              │
│  Step 2 ──────────────────── ▼
│             suggest_outfit(selected_item, wardrobe)
│                 │
│                 ├── wardrobe["items"] == []
│                 │       session["wardrobe_empty"] = True
│                 │       → tool returns generic suggestion (continues)
│                 │
│                 ├── return value == "" (unexpected failure) ────────►│
│                 │         session["error"] = "suggest_failed"        │
│                 │         Return: "Found [item] but couldn't style." │
│                 │         ◄─────────────────────────── STOP ─────────┘
│                 │
│                 └── outfit_suggestion = "Wear this with your..."
│                         session["outfit_suggestion"] = outfit_suggestion
│                              │
│  Step 3 ──────────────────── ▼
│             create_fit_card(outfit_suggestion, selected_item)
│                 │
│                 ├── missing fields → fallback caption (never stops)
│                 │
│                 └── fit_card = "thrifted this off depop for $24..."
│                         session["fit_card"] = fit_card
│                              │
│                              ▼
│                    Compose final response:
│                    - N matches found
│                    - selected_item (title, price, platform, condition, size)
│                    - outfit_suggestion
│                    - fit_card
│                    - (if wardrobe_empty) wardrobe prompt note
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
                         Return to user
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

**`search_listings`:** Give Claude the Tool 1 spec from this document (what it does, all three input parameters with types and match logic, the return value field list, and the empty-result failure mode). Also paste in the first 5 listings from `listings.json` as example data. Ask it to implement `search_listings()` using `load_listings()` from `utils/data_loader.py`. Verify before using: (1) the function accepts all three parameters and passes them correctly, (2) it filters by all three fields independently and handles `None` for size and max_price, (3) it returns a list of full listing dicts (not just titles), (4) it returns `[]` on no match — not `None` or an exception. Test with three queries: one that matches multiple listings, one that matches nothing, and one with no size or price filter.

**`suggest_outfit`:** Give Claude the Tool 2 spec (inputs, return format, empty-wardrobe handling) plus the full `wardrobe_schema.json`. Ask it to implement `suggest_outfit()` that matches `new_item["style_tags"]` and `new_item["colors"]` against wardrobe items by tag overlap and picks one bottom, one shoe, and optionally one outerwear/accessory to build the suggestion. Verify: (1) the output is a single string in second person, (2) it names wardrobe items by their `name` field, (3) when wardrobe is empty it returns a generic string (not empty, not an error), (4) it doesn't crash on a wardrobe with one item. Test with the example wardrobe plus an empty wardrobe.

**`create_fit_card`:** Give Claude the Tool 3 spec (inputs, return format, tone/style description, fallback behavior) plus 3 example captions from the interaction walkthrough below. Ask it to implement `create_fit_card()` that pulls `price` and `platform` from `new_item` and references one specific piece from the `outfit` string in the caption. Verify: (1) output is a single lowercase string under 40 words, (2) it references the platform and price, (3) it mentions at least one wardrobe piece from the outfit string, (4) when `new_item` is missing `price`, it uses the fallback caption without raising a KeyError.

**Milestone 4 — Planning loop and state management:**

Give Claude the Architecture diagram from the `## Architecture` section of this document (the full ASCII diagram) plus the State Management table and the Planning Loop section. Ask it to implement the `run_agent(user_query, wardrobe)` function that: parses the query into `description`, `size`, and `max_price`; initializes the session dict; calls each tool in order using the exact conditional branches shown in the diagram; and returns the composed final response string. Verify before using: (1) early exit on empty `search_listings` results returns the right message and does not call `suggest_outfit`, (2) `selected_item` is always `results[0]`, (3) `suggest_outfit` receives the full listing dict, not just the title, (4) the final response includes all four components (match count, item details, outfit suggestion, fit card). Run the full example query from the walkthrough below end-to-end and compare the output against the expected final output.

---

## A Complete Interaction (Step by Step)

FitFindr helps users find secondhand clothing that matches their style and budget, then shows them how to wear it. `search_listings` is triggered whenever a user describes an item they want (with optional size/price filters); `suggest_outfit` fires only after a successful search, using the returned item alongside the user's wardrobe to generate a specific styling suggestion; `create_fit_card` runs last to produce a shareable social caption. If `search_listings` returns nothing, FitFindr gives the user concrete retry advice and halts — `suggest_outfit` is never called on empty input.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query: `description="vintage graphic tee"`, `size=None` (no size mentioned), `max_price=30.0`.

It calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`.

The tool loads all 40 listings, filters to those with `price <= 30.0` and keyword/tag overlap with "vintage graphic tee" in `title`, `description`, or `style_tags`. It returns three matches sorted by relevance:
- `lst_006` — Graphic Tee, 2003 Tour Bootleg Style — $24, Depop, good condition, size L (highest match: style_tags include "graphic tee", "vintage")
- `lst_033` — Vintage Band Tee, Faded Grey — $19, Depop, fair condition, size L (style_tags include "graphic tee", "vintage", "band tee")
- `lst_002` — Y2K Baby Tee, Butterfly Print — $18, Depop, excellent condition, size S/M (style_tags include "vintage", "graphic tee")

`session["results"] = [lst_006, lst_033, lst_002]`
`session["selected_item"] = lst_006`

**Step 2:**
The agent calls `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`.

`new_item` is `lst_006`: colors `["black"]`, style_tags `["graphic tee", "vintage", "grunge", "streetwear"]`, category `"tops"`.

The wardrobe contains: baggy straight-leg dark-wash jeans (w_001, streetwear/denim), chunky white sneakers (w_007, streetwear/chunky), black combat boots (w_008, grunge/classic), vintage black denim jacket (w_006, vintage/denim), black crossbody bag (w_010, minimal/accessories).

The tool matches "streetwear" and "grunge" tags → selects w_001 (jeans) as the bottom, w_007 (chunky sneakers) as shoes (tag overlap: "streetwear"), w_006 (denim jacket) as optional outerwear (tag overlap: "vintage"), w_010 (crossbody) as finishing accessory.

`session["outfit_suggestion"]` = *"Wear the bootleg tee tucked loosely into your baggy dark-wash jeans — just the front corner — with your chunky white sneakers for a relaxed 90s streetwear look. Throw your vintage black denim jacket over the top if it's cool out. Keep the bag minimal: your black crossbody finishes it off without competing with the graphic."*

**Step 3:**
The agent calls `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.

The tool reads: platform = "depop", price = 24.0, title = "Graphic Tee — 2003 Tour Bootleg Style", outfit mentions "baggy dark-wash jeans" and "vintage black denim jacket".

`session["fit_card"]` = *"thrifted this faded bootleg tee off depop for $24 and it was literally made for my baggy jeans 🖤 vintage denim jacket doing the heavy lifting as always"*

**Final output to user:**

> Found you **3 graphic tees under $30** — top pick:
>
> 🛍️ **Graphic Tee — 2003 Tour Bootleg Style** · $24 · Depop · Good condition · Size L
>
> **How to wear it:** Wear the bootleg tee tucked loosely into your baggy dark-wash jeans — just the front corner — with your chunky white sneakers for a relaxed 90s streetwear look. Throw your vintage black denim jacket over the top if it's cool out. Keep the bag minimal: your black crossbody finishes it off without competing with the graphic.
>
> **Fit card caption:**
> *"thrifted this faded bootleg tee off depop for $24 and it was literally made for my baggy jeans 🖤 vintage denim jacket doing the heavy lifting as always"*