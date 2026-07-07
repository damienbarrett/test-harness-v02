// Host-side native tests for the New World search-results parsing core.
//
// The first test drives the SAME declarative case the central WASM harness
// runs (common/functions/new-world-product-search/parse-search-results.
// test.json), resolving its `$fixture` descriptor through the thin adapter
// in fixture-adapter.js and deep-comparing the core's result envelope
// against the case's `expected`. No schema validation happens here --
// contracts:check owns schema conformance (docs/html-parser-plan.md). The
// remaining tests pin the parsing core's edge behavior (and, because this
// language's tokenizer lives in src/ and is coverage-measured unlike the
// Python/Rust cores' library parsers, its every branch) with focused inline
// HTML fragments.

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  canonicalCardUrl,
  parseHtml,
  parseSearchResults,
  removeDotSegments,
  resolveUrl,
} from "../src/new-world-parser.js";
import { resolveFixture } from "./fixture-adapter.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..", "..");
const SUITE_PATH = path.join(
  REPO_ROOT,
  "common",
  "functions",
  "new-world-product-search",
  "parse-search-results.test.json",
);

const BASE = "https://www.newworld.co.nz/shop/search?pg=1&q=eggs";
const TITLE_AND_LINK =
  '<p data-testid="product-title">Eggs</p><a href="/shop/product/1?name=eggs">x</a>';

function pageOf(body) {
  return `<html><body><div id="search">${body}</div></body></html>`;
}

function card(testid, inner) {
  return `<div itemtype="https://schema.org/Product" data-testid="${testid}">${inner}</div>`;
}

function parsed(body) {
  const envelope = parseSearchResults(pageOf(body), BASE);
  assert.ok("ok" in envelope, JSON.stringify(envelope));
  return envelope.ok;
}

function priceGroup(dollars, cents, per) {
  return (
    '<div data-testid="price"><p data-testid="price-dollars">' +
    `${dollars}</p><p data-testid="price-cents">${cents}</p>` +
    `<p data-testid="price-per">${per}</p></div>`
  );
}

function tags(root) {
  return [...childElements(root)].map((element) => element.tag);
}

function* childElements(element) {
  for (const child of element.children) {
    if (typeof child !== "string") {
      yield child;
    }
  }
}

describe("shared contract suite", () => {
  it("matches the expected envelope for every case", () => {
    const suite = JSON.parse(readFileSync(SUITE_PATH, "utf-8"));
    for (const testCase of suite.tests) {
      const html = resolveFixture(testCase.input.html, REPO_ROOT);
      const actual = parseSearchResults(html, testCase.input["source-url"]);
      assert.deepStrictEqual(
        actual,
        testCase.expected,
        `case '${testCase.description}' diverged`,
      );
    }
  });
});

describe("result envelope", () => {
  it("returns err when the results container is absent", () => {
    const envelope = parseSearchResults(
      "<html><body><p>nothing</p></body></html>",
      BASE,
    );
    assert.deepStrictEqual(envelope, {
      err: {
        code: "no-results-container",
        message: 'no search results container (id="search") in document',
      },
    });
  });

  it("returns ok with empty products for a container with zero cards", () => {
    assert.deepStrictEqual(parsed("<p>no products match</p>"), {
      site: "new-world",
      "source-url": BASE,
      "next-page-url": null,
      products: [],
    });
  });
});

describe("card extraction", () => {
  it("extracts every field of a full card", () => {
    const body = card(
      "product-1-EA",
      '<a href="/shop/product/1?name=eggs&amp;tr=abc#frag">' +
        '<p data-testid="product-title"> Eggs <span>Dozen</span> </p>' +
        '<p data-testid="product-subtitle">12pk</p></a>' +
        '<img data-testid="product-image" src="https://img.test/1.png?w=384">' +
        priceGroup("9", "73", "ea") +
        '<p data-testid="non-promo-unit-price">$0.81/ea</p>',
    );
    assert.deepStrictEqual(parsed(body).products, [
      {
        "product-id": "1-EA",
        name: "Eggs Dozen",
        subtitle: "12pk",
        url: "https://www.newworld.co.nz/shop/product/1?name=eggs",
        "image-url": "https://img.test/1.png?w=384",
        price: { "amount-cents": 973, per: "ea", display: "$9.73" },
        "unit-price": { "amount-cents": 81, unit: "ea", display: "$0.81/ea" },
      },
    ]);
  });

  it("uses null for absent optional fields", () => {
    const [product] = parsed(card("product-2", TITLE_AND_LINK)).products;
    assert.equal(product.subtitle, null);
    assert.equal(product["image-url"], null);
    assert.equal(product.price, null);
    assert.equal(product["unit-price"], null);
  });

  it("keeps an empty subtitle element as an empty string", () => {
    const body = card(
      "product-2",
      TITLE_AND_LINK + '<p data-testid="product-subtitle"> </p>',
    );
    assert.equal(parsed(body).products[0].subtitle, "");
  });

  it("uses null for an image without src", () => {
    const body = card(
      "product-2",
      TITLE_AND_LINK + '<img data-testid="product-image">',
    );
    assert.equal(parsed(body).products[0]["image-url"], null);
  });

  it("resolves a relative image src against the source url", () => {
    const body = card(
      "product-2",
      TITLE_AND_LINK + '<img data-testid="product-image" src="/img/1.png">',
    );
    assert.equal(
      parsed(body).products[0]["image-url"],
      "https://www.newworld.co.nz/img/1.png",
    );
  });

  it("yields an empty product-id for a bare product- prefix", () => {
    const [product] = parsed(card("product-", TITLE_AND_LINK)).products;
    assert.equal(product["product-id"], "");
  });

  const incompletePrices = [
    '<div data-testid="price"><p data-testid="price-cents">73</p><p data-testid="price-per">ea</p></div>',
    '<div data-testid="price"><p data-testid="price-dollars">9</p><p data-testid="price-per">ea</p></div>',
    '<div data-testid="price"><p data-testid="price-dollars">9</p><p data-testid="price-cents">73</p></div>',
    priceGroup("nine", "73", "ea"),
    priceGroup("", "73", "ea"),
    priceGroup("9", "7", "ea"),
    priceGroup("9", "735", "ea"),
    priceGroup("9", "7x", "ea"),
    priceGroup("4294967296", "00", "ea"),
    priceGroup("42949673", "00", "ea"),
    priceGroup("42949672", "96", "ea"),
  ];
  for (const [index, group] of incompletePrices.entries()) {
    it(`treats incomplete price group #${index} as null`, () => {
      const [product] = parsed(
        card("product-2", TITLE_AND_LINK + group),
      ).products;
      assert.equal(product.price, null);
    });
  }

  it("keeps a price amount at the u32 maximum", () => {
    const body = card(
      "product-2",
      TITLE_AND_LINK + priceGroup("42949672", "95", "ea"),
    );
    assert.deepStrictEqual(parsed(body).products[0].price, {
      "amount-cents": 4294967295,
      per: "ea",
      display: "$42949672.95",
    });
  });

  const malformedUnitPrices = [
    "0.81/ea",
    "$0.81",
    "$81/ea",
    "$x.81/ea",
    "$0.8/ea",
    "$0.811/ea",
    "$0.8x/ea",
    "$0.81/",
    "$4294967296.00/ea",
    "$42949673.00/ea",
    "$42949672.96/ea",
  ];
  for (const [index, text] of malformedUnitPrices.entries()) {
    it(`treats malformed unit price #${index} as null`, () => {
      const body = card(
        "product-2",
        TITLE_AND_LINK + `<p data-testid="non-promo-unit-price">${text}</p>`,
      );
      assert.equal(parsed(body).products[0]["unit-price"], null);
    });
  }

  const skippedCards = [
    '<div itemtype="https://schema.org/Product"><p data-testid="product-title">Eggs</p><a href="/p/1">x</a></div>',
    card("item-1", TITLE_AND_LINK),
    card("product-1", '<a href="/p/1">x</a>'),
    card("product-1", '<p data-testid="product-title">Eggs</p><a>x</a>'),
  ];
  for (const [index, body] of skippedCards.entries()) {
    it(`skips a card missing required parts #${index}`, () => {
      assert.deepStrictEqual(parsed(body).products, []);
    });
  }

  it("deduplicates by canonical url in document order", () => {
    const body =
      card(
        "product-1",
        '<p data-testid="product-title">First</p><a href="/p/1?name=eggs&amp;tr=aaa">x</a>',
      ) +
      card(
        "product-2",
        '<p data-testid="product-title">Duplicate</p><a href="/p/1?name=eggs&amp;tr=bbb">x</a>',
      ) +
      card(
        "product-3",
        '<p data-testid="product-title">Distinct</p><a href="/p/2">x</a>',
      );
    assert.deepStrictEqual(
      parsed(body).products.map((p) => [p.name, p.url]),
      [
        ["First", "https://www.newworld.co.nz/p/1?name=eggs"],
        ["Distinct", "https://www.newworld.co.nz/p/2"],
      ],
    );
  });

  it("extracts cards outside the container element", () => {
    const html =
      '<html><body><div id="search"></div>' +
      card("product-9", TITLE_AND_LINK) +
      "</body></html>";
    assert.equal(parseSearchResults(html, BASE).ok.products.length, 1);
  });

  it("tolerates stray close tags", () => {
    const body = "</span>" + card("product-9", TITLE_AND_LINK) + "</table>";
    assert.equal(parsed(body).products.length, 1);
  });
});

describe("next-page link", () => {
  it("resolves the first rel=next link", () => {
    const results = parsed(
      '<a href="/elsewhere">plain</a>' +
        '<a rel="prev" href="?pg=0">prev</a>' +
        '<a rel="prefetch NEXT" href="?pg=2">next</a>' +
        '<a rel="next" href="?pg=3">later next</a>',
    );
    assert.equal(
      results["next-page-url"],
      "https://www.newworld.co.nz/shop/search?pg=2",
    );
  });

  it("skips a rel=next without href", () => {
    assert.equal(parsed('<a rel="next">no href</a>')["next-page-url"], null);
  });
});

describe("resolveUrl", () => {
  const cases = [
    ["https://other.test/x", "https://other.test/x"],
    ["mailto:someone@host.test", "mailto:someone@host.test"],
    ["//cdn.test/x", "https://cdn.test/x"],
    ["/abs/path?y=2", "https://host.test/abs/path?y=2"],
    ["?pg=2", "https://host.test/a/b?pg=2"],
    ["#frag", "https://host.test/a/b?q=1#frag"],
    ["", "https://host.test/a/b?q=1"],
    ["rel", "https://host.test/a/rel"],
    ["rel?z=3#f", "https://host.test/a/rel?z=3#f"],
    ["./rel", "https://host.test/a/rel"],
    ["../up", "https://host.test/up"],
    ["../../beyond-root", "https://host.test/beyond-root"],
    ["trailing/..", "https://host.test/a/"],
    ["trailing/.", "https://host.test/a/trailing/"],
    ["1abc:x", "https://host.test/a/1abc:x"],
    [":x", "https://host.test/a/:x"],
    ["ht~tp:x", "https://host.test/a/ht~tp:x"],
  ];
  for (const [href, expected] of cases) {
    it(`resolves ${JSON.stringify(href)}`, () => {
      assert.equal(resolveUrl("https://host.test/a/b?q=1", href), expected);
    });
  }

  it("handles degenerate bases", () => {
    assert.equal(
      resolveUrl("https://host.test/a/b?q=1#frag", "#f2"),
      "https://host.test/a/b?q=1#f2",
    );
    assert.equal(
      resolveUrl("https://host.test/a/b", "#f"),
      "https://host.test/a/b#f",
    );
    assert.equal(
      resolveUrl("https://host.test", "rel"),
      "https://host.test/rel",
    );
    assert.equal(resolveUrl("mailto:someone@host.test", "rel"), "mailto:/rel");
    assert.equal(resolveUrl("no-scheme/path", "rel"), "/no-scheme/rel");
  });
});

describe("removeDotSegments", () => {
  const cases = [
    ["/a/b/../c", "/a/c"],
    ["/a/./b", "/a/b"],
    ["/..", "/"],
    ["/a/b/..", "/a/"],
    ["/a/.", "/a/"],
    ["/a/b", "/a/b"],
  ];
  for (const [input, expected] of cases) {
    it(`normalizes ${input}`, () => {
      assert.equal(removeDotSegments(input), expected);
    });
  }
});

describe("canonicalCardUrl", () => {
  const cases = [
    ["/p/1?name=eggs&tr=zzz", "https://host.test/p/1?name=eggs"],
    ["/p/1?tr=zzz&name=eggs", "https://host.test/p/1?name=eggs"],
    ["/p/1?a=1&tr=zzz&b=2", "https://host.test/p/1?a=1&b=2"],
    ["/p/1?tr=zzz", "https://host.test/p/1"],
    ["/p/1?tr", "https://host.test/p/1"],
    ["/p/1?trx=1&x=tr", "https://host.test/p/1?trx=1&x=tr"],
    ["/p/1?a=1&&b=2", "https://host.test/p/1?a=1&&b=2"],
    ["/p/1#frag", "https://host.test/p/1"],
    ["/p/1", "https://host.test/p/1"],
  ];
  for (const [href, expected] of cases) {
    it(`canonicalizes ${href}`, () => {
      assert.equal(
        canonicalCardUrl("https://host.test/shop/search?pg=1", href),
        expected,
      );
    });
  }
});

// The tokenizer is exercised end-to-end above; these pin its individual
// branches directly (it is coverage-measured, unlike the Python/Rust cores'
// library parsers).
describe("parseHtml tokenizer", () => {
  it("skips comments, declarations and processing instructions", () => {
    assert.deepStrictEqual(
      tags(parseHtml("<!-- c --><!doctype html><?xml?><b>hi</b>")),
      ["b"],
    );
  });

  it("tolerates an unterminated comment", () => {
    assert.deepStrictEqual(tags(parseHtml("<!-- unterminated")), []);
  });

  it("tolerates an unterminated declaration", () => {
    assert.deepStrictEqual(tags(parseHtml("<!doctype")), []);
  });

  it("ignores an unmatched close tag and one without a closing bracket", () => {
    assert.deepStrictEqual(tags(parseHtml("<b></nomatch></b>")), ["b"]);
    assert.deepStrictEqual(tags(parseHtml("<b></b")), ["b"]);
  });

  it("does not push void or self-closing elements", () => {
    const root = parseHtml("<img><span/><b>x</b>");
    assert.deepStrictEqual(tags(root), ["img", "span", "b"]);
    // b is a sibling of img/span, not nested inside them.
    assert.equal(root.children.filter((c) => typeof c !== "string").length, 3);
  });

  it("treats a lone < as text when not a start tag", () => {
    const root = parseHtml("a < b<b>x</b>");
    assert.ok(root.children.includes("a "));
    assert.ok(root.children.includes("<"));
    assert.deepStrictEqual(tags(root), ["b"]);
  });

  it("keeps trailing text after the last tag", () => {
    const root = parseHtml("<b>x</b>tail");
    assert.ok(root.children.includes("tail"));
  });

  it("treats script and style content as raw text", () => {
    const root = parseHtml('<script>var x = "<div>";</script><b>y</b>');
    assert.deepStrictEqual(tags(root), ["script", "b"]);
    const [script] = childElements(root);
    assert.deepStrictEqual(script.children, ['var x = "<div>";']);
  });

  it("consumes an unclosed raw-text element to end of input", () => {
    const [script] = childElements(parseHtml("<script>tail without close"));
    assert.deepStrictEqual(script.children, ["tail without close"]);
  });

  it("consumes a raw-text element whose close tag lacks a bracket", () => {
    const [script] = childElements(parseHtml("<script>x</script"));
    assert.deepStrictEqual(script.children, ["x"]);
  });

  it("keeps an empty raw-text element childless", () => {
    const [script] = childElements(parseHtml("<script></script>"));
    assert.deepStrictEqual(script.children, []);
  });

  it("parses the attribute quoting variants", () => {
    const [el] = childElements(
      parseHtml(
        `<a d="dq" s='sq' u=uq g = "gap" flag first="1" first="2">x</a>`,
      ),
    );
    assert.deepStrictEqual(el.attrs, {
      d: "dq",
      s: "sq",
      u: "uq",
      g: "gap",
      flag: "",
      first: "1",
    });
  });

  it("ignores a stray equals with no attribute name", () => {
    const [el] = childElements(parseHtml("<a =x>y</a>"));
    assert.deepStrictEqual(el.attrs, {});
  });

  it("tolerates an unterminated start tag and unterminated quoted value", () => {
    assert.deepStrictEqual(tags(parseHtml("<div ")), ["div"]);
    const [el] = childElements(parseHtml('<a href="x'));
    assert.equal(el.attrs.href, "x");
  });

  it("decodes named, decimal, hex and unknown entities", () => {
    const [el] = childElements(
      parseHtml('<a t="&amp;&#39;&#x27;&#X27;&bogus;">&amp; &#65;</a>'),
    );
    assert.equal(el.attrs.t, "&'''&bogus;");
    assert.deepStrictEqual(el.children, ["& A"]);
  });
});
