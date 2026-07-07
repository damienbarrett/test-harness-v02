"""Host-side native tests for the New World search-results parsing core.

The first test drives the SAME declarative case the central WASM harness
runs (``common/functions/new-world-product-search/parse-search-results.
test.json``), resolving its ``$fixture`` descriptor through the thin
adapter in ``fixture_adapter.py`` and deep-comparing the core's result
envelope against the case's ``expected``. No schema validation happens
here -- ``contracts:check`` owns schema conformance
(docs/html-parser-plan.md). The remaining tests pin the parsing core's
edge behavior with focused inline HTML fragments.
"""

import json
from pathlib import Path

import pytest

import new_world_parser
from fixture_adapter import resolve_fixture
from new_world_parser import (
    canonical_card_url,
    parse_search_results,
    remove_dot_segments,
    resolve_url,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SUITE_PATH = (
    REPO_ROOT
    / "common"
    / "functions"
    / "new-world-product-search"
    / "parse-search-results.test.json"
)

BASE = "https://www.newworld.co.nz/shop/search?pg=1&q=eggs"

TITLE_AND_LINK = (
    '<p data-testid="product-title">Eggs</p><a href="/shop/product/1?name=eggs">x</a>'
)


def page(body):
    return f'<html><body><div id="search">{body}</div></body></html>'


def card(testid, inner):
    return (
        f'<div itemtype="https://schema.org/Product" data-testid="{testid}">'
        f"{inner}</div>"
    )


def parsed(body):
    envelope = parse_search_results(page(body), BASE)
    assert "ok" in envelope, envelope
    return envelope["ok"]


def price_group(dollars, cents, per):
    return (
        '<div data-testid="price"><p data-testid="price-dollars">'
        f'{dollars}</p><p data-testid="price-cents">{cents}</p>'
        f'<p data-testid="price-per">{per}</p></div>'
    )


def test_shared_suite_case_matches_expected_envelope():
    suite = json.loads(SUITE_PATH.read_text())
    for case in suite["tests"]:
        html = resolve_fixture(case["input"]["html"], REPO_ROOT)
        actual = new_world_parser.parse_search_results(
            html, case["input"]["source-url"]
        )
        assert actual == case["expected"], f"case '{case['description']}' diverged"


def test_document_without_results_container_is_a_parse_error():
    envelope = parse_search_results("<html><body><p>nothing</p></body></html>", BASE)
    assert envelope == {
        "err": {
            "code": "no-results-container",
            "message": 'no search results container (id="search") in document',
        }
    }


def test_container_with_zero_cards_is_ok_and_empty():
    results = parsed("<p>no products match</p>")
    assert results == {
        "site": "new-world",
        "source-url": BASE,
        "next-page-url": None,
        "products": [],
    }


def test_full_card_extracts_every_field():
    body = card(
        "product-1-EA",
        '<a href="/shop/product/1?name=eggs&amp;tr=abc#frag">'
        '<p data-testid="product-title"> Eggs <span>Dozen</span> </p>'
        '<p data-testid="product-subtitle">12pk</p></a>'
        '<img data-testid="product-image" src="https://img.test/1.png?w=384">'
        + price_group("9", "73", "ea")
        + '<p data-testid="non-promo-unit-price">$0.81/ea</p>',
    )
    results = parsed(body)
    assert results["products"] == [
        {
            "product-id": "1-EA",
            "name": "Eggs Dozen",
            "subtitle": "12pk",
            "url": "https://www.newworld.co.nz/shop/product/1?name=eggs",
            "image-url": "https://img.test/1.png?w=384",
            "price": {"amount-cents": 973, "per": "ea", "display": "$9.73"},
            "unit-price": {"amount-cents": 81, "unit": "ea", "display": "$0.81/ea"},
        }
    ]


def test_optional_fields_absent_become_none():
    (product,) = parsed(card("product-2", TITLE_AND_LINK))["products"]
    assert product["subtitle"] is None
    assert product["image-url"] is None
    assert product["price"] is None
    assert product["unit-price"] is None


def test_empty_subtitle_element_is_kept_as_empty_string():
    body = card("product-2", TITLE_AND_LINK + '<p data-testid="product-subtitle"> </p>')
    (product,) = parsed(body)["products"]
    assert product["subtitle"] == ""


def test_image_without_src_is_none():
    body = card("product-2", TITLE_AND_LINK + '<img data-testid="product-image">')
    (product,) = parsed(body)["products"]
    assert product["image-url"] is None


def test_relative_image_src_resolves_against_source_url():
    body = card(
        "product-2",
        TITLE_AND_LINK + '<img data-testid="product-image" src="/img/1.png">',
    )
    (product,) = parsed(body)["products"]
    assert product["image-url"] == "https://www.newworld.co.nz/img/1.png"


@pytest.mark.parametrize(
    "group",
    [
        # missing dollars / cents / per elements inside the group
        '<div data-testid="price"><p data-testid="price-cents">73</p>'
        '<p data-testid="price-per">ea</p></div>',
        '<div data-testid="price"><p data-testid="price-dollars">9</p>'
        '<p data-testid="price-per">ea</p></div>',
        '<div data-testid="price"><p data-testid="price-dollars">9</p>'
        '<p data-testid="price-cents">73</p></div>',
        # malformed digit content
        price_group("nine", "73", "ea"),
        price_group("", "73", "ea"),
        price_group("9", "7", "ea"),
        price_group("9", "735", "ea"),
        price_group("9", "7x", "ea"),
        # beyond the WIT u32 amount-cents bound
        price_group("4294967296", "00", "ea"),
        price_group("42949673", "00", "ea"),
        price_group("42949672", "96", "ea"),
    ],
)
def test_incomplete_price_groups_are_none(group):
    (product,) = parsed(card("product-2", TITLE_AND_LINK + group))["products"]
    assert product["price"] is None


def test_price_amount_at_u32_maximum_is_kept():
    body = card("product-2", TITLE_AND_LINK + price_group("42949672", "95", "ea"))
    (product,) = parsed(body)["products"]
    assert product["price"] == {
        "amount-cents": 4294967295,
        "per": "ea",
        "display": "$42949672.95",
    }


@pytest.mark.parametrize(
    "text",
    [
        "0.81/ea",  # no $ prefix
        "$0.81",  # no unit separator
        "$81/ea",  # no decimal point
        "$x.81/ea",  # non-digit dollars
        "$0.8/ea",  # one-digit cents
        "$0.811/ea",  # three-digit cents
        "$0.8x/ea",  # non-digit cents
        "$0.81/",  # empty unit
        "$4294967296.00/ea",  # beyond u32
        "$42949673.00/ea",  # beyond u32 after *100
        "$42949672.96/ea",  # beyond u32 after +cents
    ],
)
def test_malformed_unit_price_texts_are_none(text):
    body = card(
        "product-2",
        TITLE_AND_LINK + f'<p data-testid="non-promo-unit-price">{text}</p>',
    )
    (product,) = parsed(body)["products"]
    assert product["unit-price"] is None


@pytest.mark.parametrize(
    "body",
    [
        # no data-testid on the Product element itself
        '<div itemtype="https://schema.org/Product">'
        '<p data-testid="product-title">Eggs</p><a href="/p/1">x</a></div>',
        # data-testid without the product- prefix
        card("item-1", TITLE_AND_LINK),
        # no product-title
        card("product-1", '<a href="/p/1">x</a>'),
        # no link with an href
        card("product-1", '<p data-testid="product-title">Eggs</p><a>x</a>'),
    ],
)
def test_cards_missing_required_parts_are_skipped(body):
    assert parsed(body)["products"] == []


def test_bare_product_prefix_yields_empty_product_id():
    (product,) = parsed(card("product-", TITLE_AND_LINK))["products"]
    assert product["product-id"] == ""


def test_cards_are_deduplicated_by_canonical_url_in_document_order():
    body = (
        card(
            "product-1",
            '<p data-testid="product-title">First</p>'
            '<a href="/p/1?name=eggs&amp;tr=aaa">x</a>',
        )
        + card(
            "product-2",
            '<p data-testid="product-title">Duplicate</p>'
            '<a href="/p/1?name=eggs&amp;tr=bbb">x</a>',
        )
        + card(
            "product-3",
            '<p data-testid="product-title">Distinct</p><a href="/p/2">x</a>',
        )
    )
    products = parsed(body)["products"]
    assert [(p["name"], p["url"]) for p in products] == [
        ("First", "https://www.newworld.co.nz/p/1?name=eggs"),
        ("Distinct", "https://www.newworld.co.nz/p/2"),
    ]


def test_cards_outside_the_container_are_still_extracted():
    html = (
        '<html><body><div id="search"></div>'
        + card("product-9", TITLE_AND_LINK)
        + "</body></html>"
    )
    envelope = parse_search_results(html, BASE)
    assert len(envelope["ok"]["products"]) == 1


def test_stray_close_tags_are_tolerated():
    body = "</span>" + card("product-9", TITLE_AND_LINK) + "</table>"
    assert len(parsed(body)["products"]) == 1


def test_next_page_link_is_resolved_and_first_match_wins():
    results = parsed(
        '<a href="/elsewhere">plain</a>'
        '<a rel="prev" href="?pg=0">prev</a>'
        '<a rel="prefetch NEXT" href="?pg=2">next</a>'
        '<a rel="next" href="?pg=3">later next</a>'
    )
    assert results["next-page-url"] == "https://www.newworld.co.nz/shop/search?pg=2"


def test_next_rel_without_href_is_skipped():
    assert parsed('<a rel="next">no href</a>')["next-page-url"] is None


@pytest.mark.parametrize(
    "href,expected",
    [
        ("https://other.test/x", "https://other.test/x"),
        ("mailto:someone@host.test", "mailto:someone@host.test"),
        ("//cdn.test/x", "https://cdn.test/x"),
        ("/abs/path?y=2", "https://host.test/abs/path?y=2"),
        ("?pg=2", "https://host.test/a/b?pg=2"),
        ("#frag", "https://host.test/a/b?q=1#frag"),
        ("", "https://host.test/a/b?q=1"),
        ("rel", "https://host.test/a/rel"),
        ("rel?z=3#f", "https://host.test/a/rel?z=3#f"),
        ("./rel", "https://host.test/a/rel"),
        ("../up", "https://host.test/up"),
        ("../../beyond-root", "https://host.test/beyond-root"),
        ("trailing/..", "https://host.test/a/"),
        ("trailing/.", "https://host.test/a/trailing/"),
        # not absolute URLs: scheme must start alphabetic and use valid chars
        ("1abc:x", "https://host.test/a/1abc:x"),
        (":x", "https://host.test/a/:x"),
        ("ht~tp:x", "https://host.test/a/ht~tp:x"),
    ],
)
def test_resolve_url_handles_every_reference_form(href, expected):
    assert resolve_url("https://host.test/a/b?q=1", href) == expected


def test_resolve_url_handles_degenerate_bases():
    assert (
        resolve_url("https://host.test/a/b?q=1#frag", "#f2")
        == "https://host.test/a/b?q=1#f2"
    )
    assert resolve_url("https://host.test/a/b", "#f") == "https://host.test/a/b#f"
    assert resolve_url("https://host.test", "rel") == "https://host.test/rel"
    assert resolve_url("mailto:someone@host.test", "rel") == "mailto:/rel"
    assert resolve_url("no-scheme/path", "rel") == "/no-scheme/rel"


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/a/b/../c", "/a/c"),
        ("/a/./b", "/a/b"),
        ("/..", "/"),
        ("/a/b/..", "/a/"),
        ("/a/.", "/a/"),
        ("/a/b", "/a/b"),
    ],
)
def test_remove_dot_segments_normalizes_paths(path, expected):
    assert remove_dot_segments(path) == expected


@pytest.mark.parametrize(
    "href,expected",
    [
        ("/p/1?name=eggs&tr=zzz", "https://host.test/p/1?name=eggs"),
        ("/p/1?tr=zzz&name=eggs", "https://host.test/p/1?name=eggs"),
        ("/p/1?a=1&tr=zzz&b=2", "https://host.test/p/1?a=1&b=2"),
        ("/p/1?tr=zzz", "https://host.test/p/1"),
        ("/p/1?tr", "https://host.test/p/1"),
        ("/p/1?trx=1&x=tr", "https://host.test/p/1?trx=1&x=tr"),
        ("/p/1?a=1&&b=2", "https://host.test/p/1?a=1&&b=2"),
        ("/p/1#frag", "https://host.test/p/1"),
        ("/p/1", "https://host.test/p/1"),
    ],
)
def test_canonical_card_url_strips_tr_and_fragment_only(href, expected):
    assert canonical_card_url("https://host.test/shop/search?pg=1", href) == expected
