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
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): ...
- `size` (str): ...
- `max_price` (float): ...

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): ...
- `wardrobe` (dict): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (...): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Milestone 4 — Planning loop and state management:**

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

FitFindr helps users find secondhand clothing that matches their style and budget, then shows them how to wear it. search_listings is triggered whenever a user describes an item they want (with optional size/price filters); suggest_outfit fires only after a successful search, using the returned item alongside the user's wardrobe to generate a specific styling suggestion; create_fit_card runs last to produce a shareable social caption. If search_listings returns nothing, FitFindr gives the user concrete retry advice and halts. suggest_outfit is never called on empty input.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent calls `search_listings("vintage graphic tee", max_price=30.0)`.
The tool filters listings.json against the query and price cap. It returns three matches sorted by relevance:
- lst_006 — Graphic Tee, 2003 Tour Bootleg Style — $24, Depop, good condition, size L
- lst_033 — Vintage Band Tee, Faded Grey — $19, Depop, fair condition, size L
- lst_002 — Y2K Baby Tee, Butterfly Print — $18, Depop, excellent condition, size S/M

The agent picks the top result: **lst_006, Graphic Tee (2003 Tour Bootleg Style) — $24, Depop, good condition.**

**Step 2:**
The agent calls `suggest_outfit(new_item=lst_006, wardrobe=example_wardrobe)`.
It passes the new tee (black, boxy fit; style tags: graphic tee, vintage, grunge, streetwear) alongside the user's wardrobe, which includes baggy straight-leg jeans (w_001), chunky white sneakers (w_007), black combat boots (w_008), a vintage black denim jacket (w_006), and a black crossbody bag (w_010).

The tool returns: *"Wear the bootleg tee tucked loosely into your baggy dark-wash jeans — just the front corner — with your chunky white sneakers for a relaxed 90s streetwear look. Throw your vintage black denim jacket over the top if it's cool out. Keep the bag minimal: your black crossbody finishes it off without competing with the graphic."*

**Step 3:**
The agent calls `create_fit_card(outfit=<suggestion above>, new_item=lst_006)`.
It returns a ready-to-post social caption based on the outfit and the thrift find.

**Final output to user:**

> Found you **3 graphic tees under $30** — top pick:
> 
> 🛍️ **Graphic Tee — 2003 Tour Bootleg Style** · $24 · Depop · Good condition · Size L
> 
> **How to wear it:** Tuck the front corner loosely into your baggy dark-wash jeans with your chunky white sneakers. Throw your vintage black denim jacket over the top if it's cool out. Black crossbody keeps it clean.
> 
> **Fit card caption:**
> *"thrifted this faded bootleg tee off depop for $24 and it was literally made for my baggy jeans 🖤 vintage denim jacket doing the heavy lifting as always"*
