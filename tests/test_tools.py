"""
tests/test_tools.py

Tests for each tool's happy path and failure mode.
Run with: pytest tests/
"""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", max_price=30)
    assert all(item["price"] <= 30 for item in results)

def test_search_no_exception_on_impossible_query():
    # Should return empty list, not raise
    try:
        results = search_listings("zzznomatch", size="ZZZ", max_price=0.01)
        assert results == []
    except Exception:
        assert False, "search_listings raised an exception on no-match query"


# ── suggest_outfit tests ──────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", max_price=30)
    assert results, "Need at least one result to test suggest_outfit"
    response = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(response, str)
    assert len(response) > 0

def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", max_price=30)
    assert results, "Need at least one result to test suggest_outfit"
    response = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(response, str)
    assert len(response) > 0


# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    results = search_listings("vintage graphic tee", max_price=30)
    assert results
    outfit = suggest_outfit(results[0], get_example_wardrobe())
    card = create_fit_card(outfit, results[0])
    assert isinstance(card, str)
    assert len(card) > 0

def test_create_fit_card_empty_outfit():
    results = search_listings("vintage graphic tee", max_price=30)
    assert results
    card = create_fit_card("", results[0])
    assert "Could not generate a fit card" in card

def test_create_fit_card_whitespace_outfit():
    results = search_listings("vintage graphic tee", max_price=30)
    assert results
    card = create_fit_card("   ", results[0])
    assert "Could not generate a fit card" in card
