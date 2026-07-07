// Tests for the thin component glue (src/new-world-parser.js): it adapts the
// language-neutral core envelope to jco's camelCase binding shape, returns
// the ok value, and throws the err value (componentize-js's `result<T, E>`
// convention). The central WASM harness proves the compiled component end to
// end; these cover the glue's own conversion branches at the source level.

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { newWorldProductSearch } from "../src/new-world-parser.js";

const BASE = "https://www.newworld.co.nz/shop/search?pg=1";

function page(body) {
  return `<html><body><div id="search">${body}</div></body></html>`;
}

const FULL_CARD =
  '<div itemtype="https://schema.org/Product" data-testid="product-1-EA">' +
  '<a href="/shop/product/1?name=eggs"><p data-testid="product-title">Eggs</p>' +
  '<p data-testid="product-subtitle">12pk</p></a>' +
  '<img data-testid="product-image" src="/img/1.png">' +
  '<div data-testid="price"><p data-testid="price-dollars">9</p>' +
  '<p data-testid="price-cents">73</p><p data-testid="price-per">ea</p></div>' +
  '<p data-testid="non-promo-unit-price">$0.81/ea</p></div>';

const BARE_CARD =
  '<div itemtype="https://schema.org/Product" data-testid="product-2">' +
  '<p data-testid="product-title">Plain</p><a href="/p/2">x</a></div>';

describe("newWorldProductSearch.parseSearchResults", () => {
  it("returns camelCase records with populated optionals", () => {
    const result = newWorldProductSearch.parseSearchResults(
      page(FULL_CARD + '<a rel="next" href="?pg=2">next</a>'),
      BASE,
    );
    assert.deepStrictEqual(result, {
      site: "new-world",
      sourceUrl: BASE,
      nextPageUrl: "https://www.newworld.co.nz/shop/search?pg=2",
      products: [
        {
          productId: "1-EA",
          name: "Eggs",
          subtitle: "12pk",
          url: "https://www.newworld.co.nz/shop/product/1?name=eggs",
          imageUrl: "https://www.newworld.co.nz/img/1.png",
          price: { amountCents: 973, per: "ea", display: "$9.73" },
          unitPrice: { amountCents: 81, unit: "ea", display: "$0.81/ea" },
        },
      ],
    });
  });

  it("maps absent optionals to undefined", () => {
    const result = newWorldProductSearch.parseSearchResults(
      page(BARE_CARD),
      BASE,
    );
    assert.equal(result.nextPageUrl, undefined);
    const [product] = result.products;
    assert.equal(product.subtitle, undefined);
    assert.equal(product.imageUrl, undefined);
    assert.equal(product.price, undefined);
    assert.equal(product.unitPrice, undefined);
  });

  it("throws the parse-error value for the err branch", () => {
    assert.throws(
      () =>
        newWorldProductSearch.parseSearchResults("<p>no container</p>", BASE),
      (thrown) => {
        assert.deepStrictEqual(thrown, {
          code: "no-results-container",
          message: 'no search results container (id="search") in document',
        });
        return true;
      },
    );
  });
});
