"""Component entry point for the ``new-world-parser`` world.

Thin glue only: the parsing logic lives in ``new_world_parser`` (the one
per-language core, shared with the host-side native tests); this module
converts the core's plain-dict result envelope into the wit-bindgen
dataclasses componentize-py marshals across the component boundary, raising
``componentize_py_types.Err`` for the ``result<..., parse-error>`` err
branch as the generated bindings document.
"""

from componentize_py_types import Err
from wit_world import exports
from wit_world.exports.new_world_product_search import (
    ParseError,
    Price,
    ProductCard,
    SearchResults,
    UnitPrice,
)

import new_world_parser


def _to_price(price: dict | None) -> Price | None:
    if price is None:
        return None
    return Price(
        amount_cents=price["amount-cents"],
        per=price["per"],
        display=price["display"],
    )


def _to_unit_price(unit_price: dict | None) -> UnitPrice | None:
    if unit_price is None:
        return None
    return UnitPrice(
        amount_cents=unit_price["amount-cents"],
        unit=unit_price["unit"],
        display=unit_price["display"],
    )


def _to_product_card(card: dict) -> ProductCard:
    return ProductCard(
        product_id=card["product-id"],
        name=card["name"],
        subtitle=card["subtitle"],
        url=card["url"],
        image_url=card["image-url"],
        price=_to_price(card["price"]),
        unit_price=_to_unit_price(card["unit-price"]),
    )


class NewWorldProductSearch(exports.NewWorldProductSearch):
    def parse_search_results(self, html: str, source_url: str) -> SearchResults:
        envelope = new_world_parser.parse_search_results(html, source_url)
        if "err" in envelope:
            error = envelope["err"]
            raise Err(ParseError(code=error["code"], message=error["message"]))
        results = envelope["ok"]
        return SearchResults(
            site=results["site"],
            source_url=results["source-url"],
            next_page_url=results["next-page-url"],
            products=[_to_product_card(card) for card in results["products"]],
        )
