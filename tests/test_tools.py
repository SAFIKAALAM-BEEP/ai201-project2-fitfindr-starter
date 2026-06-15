"""
tests/test_tools.py

Pytest tests for the three FitFindr tools.

Run with:
    pytest tests/test_tools.py -v

Tests that call the LLM (suggest_outfit, create_fit_card) are marked with
@pytest.mark.llm so you can skip them during offline development:
    pytest tests/test_tools.py -v -m "not llm"
"""

import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ═══════════════════════════════════════════════════════════
# search_listings — no LLM, always safe to run
# ═══════════════════════════════════════════════════════════

class TestSearchListings:

    def test_returns_results_for_known_query(self):
        """Happy path — a broad query should return at least one result."""
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_empty_results_no_exception(self):
        """No-results path — should return [] not raise."""
        results = search_listings("designer ballgown", size="XXS", max_price=5)
        assert results == []

    def test_price_filter_respected(self):
        """Every returned item must be at or below max_price."""
        results = search_listings("jacket", size=None, max_price=10)
        assert all(item["price"] <= 10 for item in results)

    def test_price_filter_none_returns_more_than_strict_filter(self):
        """Removing the price filter should return at least as many results."""
        filtered = search_listings("vintage", size=None, max_price=20)
        unfiltered = search_listings("vintage", size=None, max_price=None)
        assert len(unfiltered) >= len(filtered)

    def test_size_filter_case_insensitive(self):
        """Size filter should match regardless of case."""
        results_upper = search_listings("tee", size="M", max_price=None)
        results_lower = search_listings("tee", size="m", max_price=None)
        assert len(results_upper) == len(results_lower)

    def test_size_filter_substring_match(self):
        """'M' should match listings whose size field contains 'M' (e.g. 'S/M', 'M/L')."""
        results = search_listings("top", size="M", max_price=None)
        for item in results:
            assert "m" in item["size"].lower()

    def test_result_contains_required_fields(self):
        """Each returned dict must have all expected listing fields."""
        results = search_listings("vintage tee", size=None, max_price=None)
        assert len(results) > 0
        required = {"id", "title", "description", "category", "style_tags",
                    "size", "condition", "price", "colors", "platform"}
        for item in results:
            assert required.issubset(item.keys()), f"Missing fields in: {item}"

    def test_nonexistent_query_returns_empty_list(self):
        """Completely nonsense query returns [] without crashing."""
        results = search_listings("xyzabc123nonexistent", size=None, max_price=None)
        assert results == []

    def test_returns_list_of_dicts(self):
        """Return type is always list[dict], even for partial matches."""
        results = search_listings("boots", size=None, max_price=None)
        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, dict)


# ═══════════════════════════════════════════════════════════
# suggest_outfit — calls Groq LLM
# ═══════════════════════════════════════════════════════════

@pytest.mark.llm
class TestSuggestOutfit:

    def _get_item(self):
        """Helper — grab a known listing to use as the new item."""
        results = search_listings("vintage graphic tee", size=None, max_price=None)
        assert results, "Need at least one listing to test suggest_outfit"
        return results[0]

    def test_returns_nonempty_string_with_wardrobe(self):
        """With a populated wardrobe, should return a non-empty string."""
        item = self._get_item()
        result = suggest_outfit(item, get_example_wardrobe())
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_empty_wardrobe_does_not_crash(self):
        """Empty wardrobe must not raise — should return general styling advice."""
        item = self._get_item()
        result = suggest_outfit(item, get_empty_wardrobe())
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_empty_wardrobe_returns_generic_advice(self):
        """With no wardrobe items, suggestion should still be usable."""
        item = self._get_item()
        result = suggest_outfit(item, get_empty_wardrobe())
        assert len(result.split()) >= 10

    def test_result_is_string_not_dict(self):
        """Return value must be a plain string, not a dict or LLM response object."""
        item = self._get_item()
        result = suggest_outfit(item, get_example_wardrobe())
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════
# create_fit_card — calls Groq LLM
# ═══════════════════════════════════════════════════════════

@pytest.mark.llm
class TestCreateFitCard:

    def _get_item(self):
        results = search_listings("vintage tee", size=None, max_price=None)
        assert results
        return results[0]

    def test_returns_nonempty_string(self):
        """Normal inputs → non-empty caption string."""
        item = self._get_item()
        result = create_fit_card("Pair with baggy jeans and chunky sneakers.", item)
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_empty_outfit_returns_error_string_not_exception(self):
        """Empty outfit string must return an error message, not crash."""
        item = self._get_item()
        result = create_fit_card("", item)
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_whitespace_outfit_returns_error_string(self):
        """Whitespace-only outfit is treated the same as empty."""
        item = self._get_item()
        result = create_fit_card("   ", item)
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_captions_vary_across_runs(self):
        """Higher temperature means repeated calls on same input produce different output."""
        item = self._get_item()
        outfit = "Wear with your baggy dark-wash jeans and chunky white sneakers."
        captions = {create_fit_card(outfit, item) for _ in range(3)}
        assert len(captions) > 1, "Captions should vary across runs — check LLM temperature"

    def test_result_is_string_not_dict(self):
        """Return type is always str."""
        item = self._get_item()
        result = create_fit_card("Classic outfit suggestion here.", item)
        assert isinstance(result, str)