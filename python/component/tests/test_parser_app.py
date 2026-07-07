"""Host-side contract tests for the Python parser component entry point.

These tests import the *real* wit-bindgen-generated ``wit_world`` bindings
(the merged two-world package emitted to ``../bindings/`` at build time;
made importable via ``conftest.py``) and exercise
``parser_app.NewWorldProductSearch`` end to end: the ok branch must produce
the generated dataclass tree, and the err branch must raise
``componentize_py_types.Err`` carrying a ``ParseError`` -- exactly the
convention the generated ``NewWorldProductSearch`` protocol documents.
The parsing logic itself is pinned by ``test_new_world_parser.py``; this
file pins the glue that gets compiled into ``new-world-parser.wasm``.
"""

import pytest
from componentize_py_types import Err
from wit_world.exports.new_world_product_search import (
    ParseError,
    Price,
    ProductCard,
    SearchResults,
    UnitPrice,
)

from parser_app import NewWorldProductSearch

BASE = "https://www.newworld.co.nz/shop/search?pg=1&q=eggs"

PAGE = """
<html><body><div id="search">
  <div itemtype="https://schema.org/Product" data-testid="product-1-EA">
    <a href="/shop/product/1?name=eggs&amp;tr=abc">
      <p data-testid="product-title">Eggs</p>
      <p data-testid="product-subtitle">12pk</p>
    </a>
    <img data-testid="product-image" src="https://img.test/1.png">
    <div data-testid="price">
      <p data-testid="price-dollars">9</p>
      <p data-testid="price-cents">73</p>
      <p data-testid="price-per">ea</p>
    </div>
    <p data-testid="non-promo-unit-price">$0.81/ea</p>
  </div>
  <div itemtype="https://schema.org/Product" data-testid="product-2-EA">
    <p data-testid="product-title">Bare</p>
    <a href="/shop/product/2">x</a>
  </div>
  <a rel="next" href="?pg=2">next</a>
</div></body></html>
"""


def test_ok_branch_returns_generated_dataclasses():
    actual = NewWorldProductSearch().parse_search_results(PAGE, BASE)
    assert actual == SearchResults(
        site="new-world",
        source_url=BASE,
        next_page_url="https://www.newworld.co.nz/shop/search?pg=2",
        products=[
            ProductCard(
                product_id="1-EA",
                name="Eggs",
                subtitle="12pk",
                url="https://www.newworld.co.nz/shop/product/1?name=eggs",
                image_url="https://img.test/1.png",
                price=Price(amount_cents=973, per="ea", display="$9.73"),
                unit_price=UnitPrice(amount_cents=81, unit="ea", display="$0.81/ea"),
            ),
            ProductCard(
                product_id="2-EA",
                name="Bare",
                subtitle=None,
                url="https://www.newworld.co.nz/shop/product/2",
                image_url=None,
                price=None,
                unit_price=None,
            ),
        ],
    )


def test_err_branch_raises_err_with_parse_error_payload():
    with pytest.raises(Err) as excinfo:
        NewWorldProductSearch().parse_search_results(
            "<html><body><p>not a search page</p></body></html>", BASE
        )
    assert excinfo.value.value == ParseError(
        code="no-results-container",
        message='no search results container (id="search") in document',
    )
