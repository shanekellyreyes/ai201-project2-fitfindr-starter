# FitFindr

A multi-tool AI agent that helps users find secondhand pieces and figure out how to wear them. FitFindr searches mock thrift listings, suggests outfit combinations based on the user's wardrobe, and generates a shareable fit card caption — all from a single natural language query.

---

## How to Run

```bash
# 1. Clone and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Groq API key
echo "GROQ_API_KEY=your_key_here" > .env

# 4. Launch the app
python app.py
# Open http://localhost:7860
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`
- **Purpose:** Searches the mock listings dataset for secondhand items matching the user's description, optionally filtered by size and price ceiling.
- **Inputs:**
  - `description` (str): Keywords describing the item (e.g. "vintage graphic tee")
  - `size` (str | None): Size string to filter by (e.g. "M", "S/M") — None skips size filtering
  - `max_price` (float | None): Maximum price inclusive — None skips price filtering
- **Output:** A list of matching listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list if nothing matches — never raises an exception.

---

### `suggest_outfit(new_item, wardrobe)`
- **Purpose:** Given a thrifted item and the user's existing wardrobe, uses the LLM to suggest 1–2 complete outfit combinations.
- **Inputs:**
  - `new_item` (dict): A listing dict for the item the user found
  - `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. May be empty.
- **Output:** A non-empty string with outfit suggestions. If the wardrobe is empty, returns general styling advice instead of wardrobe-specific combinations.

---

### `create_fit_card(outfit, new_item)`
- **Purpose:** Generates a short 2–4 sentence shareable caption for the outfit — the kind of thing someone would post on Instagram or TikTok with their OOTD.
- **Inputs:**
  - `outfit` (str): The outfit suggestion string from `suggest_outfit()`
  - `new_item` (dict): The listing dict for the thrifted item
- **Output:** A casual, authentic 2–4 sentence caption that mentions the item name, price, and platform naturally. Returns an error message string if `outfit` is empty — does not raise an exception.

---

## How the Planning Loop Works

The agent follows this conditional logic in `run_agent()`:

1. **Parse the query** using the LLM to extract `description`, `size`, and `max_price` as structured fields. Falls back to regex if the LLM call fails.

2. **Call `search_listings()`** with the parsed parameters.
   - If results are **empty** → set `session["error"]` to a helpful message and **return early**. `suggest_outfit` and `create_fit_card` are never called.
   - If results are **not empty** → set `session["selected_item"] = results[0]` and continue.

3. **Call `suggest_outfit()`** with the selected item and the user's wardrobe. Store the result in `session["outfit_suggestion"]`.

4. **Call `create_fit_card()`** with the outfit suggestion and selected item. Store the result in `session["fit_card"]`.

5. **Return the completed session.**

The agent never calls all three tools unconditionally — it branches at step 2. Each subsequent tool only runs if the previous step succeeded.

---

## State Management

All state is stored in the session dict initialized by `_new_session()` in `agent.py`. Fields:

| Field | Set when | Passed to |
|-------|----------|-----------|
| `session["query"]` | Start | Never modified |
| `session["parsed"]` | After query parse | Used to call `search_listings` |
| `session["search_results"]` | After `search_listings` | Used to select top item |
| `session["selected_item"]` | After selecting `results[0]` | `suggest_outfit`, `create_fit_card` |
| `session["wardrobe"]` | Start (passed in) | `suggest_outfit` |
| `session["outfit_suggestion"]` | After `suggest_outfit` | `create_fit_card` |
| `session["fit_card"]` | After `create_fit_card` | Returned to UI |
| `session["error"]` | On any early exit | Displayed in panel 1 |

No tool receives the raw user query — everything flows through the session dict. `app.py` reads from the session to populate the three output panels.

---

## Error Handling

### `search_listings` — no results
If the query returns no matches, the agent sets `session["error"]` and returns immediately without calling the other tools.

**Triggered by:**
```bash
python -c "
from agent import run_agent
from utils.data_loader import get_example_wardrobe
session = run_agent('designer ballgown size XXS under \$5', get_example_wardrobe())
print(session['error'])
"
```
**Agent response:** `"No listings found for that search. Try broadening your description, adjusting the size, or raising the price limit."`

---

### `suggest_outfit` — empty wardrobe
If the user has no wardrobe items, the tool switches to a general styling prompt instead of a wardrobe-specific one. It never crashes or returns an empty string.

**Triggered by:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', max_price=30)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
```
**Agent response:** `"First, let's talk about embracing that Y2K vibe. You could pair this baby tee with some low-rise jeans or a flowy skirt... The fitted crop length of the tee will add a cool, nostalgic touch..."`

---

### `create_fit_card` — empty outfit string
If `outfit` is empty or whitespace, the tool returns a descriptive error string without calling the LLM.

**Triggered by:**
```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', max_price=30)
print(create_fit_card('', results[0]))
"
```
**Agent response:** `"Could not generate a fit card — outfit description was missing."`

---

## Query Interface

**Tool:** Gradio web app (`app.py`)
**Run:** `python app.py` → open http://localhost:7860

**Inputs:**
- "What are you looking for?" — free-text query (description, size, price all accepted)
- "Wardrobe" radio — "Example wardrobe" or "Empty wardrobe (new user)"

**Outputs:**
- 🛍️ Top listing found — formatted listing with title, price, platform, size, condition, and description
- 👗 Outfit idea — outfit suggestion from `suggest_outfit`
- ✨ Your fit card — shareable caption from `create_fit_card`

If the search returns no results, the error message appears in panel 1 and panels 2 and 3 are empty.

**Sample interaction transcript:**

> **Input:** vintage graphic tee under $30
> **Wardrobe:** Example wardrobe
>
> **🛍️ Top listing found:**
> Y2K Baby Tee — Butterfly Print
> 💰 $18.0 on Depop
> 📏 Size: S/M
> ✅ Condition: Excellent
> Super cute early 2000s baby tee with butterfly graphic. Fitted crop length.
>
> **👗 Outfit idea:**
> First, let's pair it with those baggy straight-leg jeans and the chunky white sneakers. The fitted crop length of the tee will create a cool contrast with the loose, relaxed fit of the jeans...
>
> **✨ Your fit card:**
> I just scored the cutest Y2K Baby Tee on Depop for $18.0 and I'm obsessed with how it looks paired with my baggy straight-leg jeans and chunky white sneakers...

---

## Spec Reflection

**One way the spec helped:** Writing the planning loop as explicit conditional logic in planning.md before touching agent.py made the branching structure clear before any code was written. The specific condition — "if results is empty, set session['error'] and return early, do NOT proceed to suggest_outfit" — translated directly into code with no ambiguity.

**One way implementation diverged:** The spec described query parsing as a simple LLM extraction step, but the implementation also includes a regex fallback for when the LLM call fails. This wasn't in the original spec — it was added during implementation to make the agent more resilient. The planning.md doesn't mention the fallback, so it diverges there.

---

## AI Usage

**Instance 1**
- *What I gave Claude:* The Tool 1 spec from planning.md (inputs, return value, failure mode) and `utils/data_loader.py`
- *What it produced:* `search_listings()` using `load_listings()`, filtering by price and size, scoring by keyword overlap, returning sorted results
- *What I changed:* Tested with 3 queries — a matching query, a tight price filter, and an impossible query. Confirmed it returns an empty list on no match rather than raising an exception before trusting it.

**Instance 2**
- *What I gave Claude:* The Planning Loop and State Management sections from planning.md plus the Architecture diagram
- *What it produced:* `run_agent()` in agent.py with the session dict, LLM-based query parser with regex fallback, and the conditional branch on empty search results
- *What I changed:* Verified the no-results branch worked by running the ballgown test case and confirming `session["fit_card"]` was None and `session["error"]` was set before accepting the implementation.