// Parsing core for the `new-world-product-search` WIT interface
// (common/wit/html-parser.wit).
//
// One parsing core per language (docs/html-parser-plan.md): this module is
// used directly by the host-side native tests in tests/ and compiled
// unchanged into new-world-parser.wasm. The pure extraction logic and the
// thin WIT-binding glue (the `newWorldProductSearch` export at the end of
// this file) share one module because componentize-js evaluates a single
// self-contained entry and does not resolve relative imports -- there is
// never a second copy of the extraction logic in this language.
//
// The HTML tree is built with a small hand-rolled tolerant tokenizer rather
// than a third-party parser (parse5): constitution section 6.3 keeps the
// component pure and dependency-free, jco componentize only has to bundle a
// single self-contained ESM module, and porting the exact same
// tokenizer the Python core uses (stdlib html.parser) keeps the structured
// output -- and therefore the deduplication keys -- byte-identical across
// all three implementations. `parse_search_results` returns the harness-wide
// result envelope directly: `{ok: {...}}` or `{err: {...}}`, every record a
// plain object keyed exactly like the JSON contract (kebab-case, `null` for
// an absent WIT `option<>`).
//
// URL resolution is a small explicit RFC-3986-style resolver implemented
// identically in all three language cores (rather than each language's URL
// library) so canonical URLs -- and therefore dedup keys -- match
// byte-for-byte across implementations.

const SITE = "new-world";
const PRODUCT_ITEMTYPE = "https://schema.org/Product";
const PRODUCT_TESTID_PREFIX = "product-";
const U32_MAX = 4294967295;

// The element that makes a document recognizable as a search-results page.
// The captured New World page wraps its results section in id="search"; a
// document without it yields err(no-results-container), while a page with
// the container but zero product cards is ok with empty products.
const RESULTS_CONTAINER_ID = "search";
const NO_RESULTS_CONTAINER_CODE = "no-results-container";
const NO_RESULTS_CONTAINER_MESSAGE =
  'no search results container (id="search") in document';

// Void elements never take a closing tag and must not be pushed onto the
// open-element stack (mirrors the html5ever/html.parser behavior).
const VOID_ELEMENTS = new Set([
  "area",
  "base",
  "br",
  "col",
  "embed",
  "hr",
  "img",
  "input",
  "link",
  "meta",
  "param",
  "source",
  "track",
  "wbr",
]);

// Raw-text elements: their content is text, never markup, so the tokenizer
// consumes everything up to the matching close tag without parsing tags
// inside (matches html.parser's CDATA handling; keeps the big inline Next.js
// <script> JSON from corrupting the element tree).
const RAWTEXT_ELEMENTS = new Set(["script", "style", "textarea", "title"]);

const NAMED_ENTITIES = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
};

function decodeEntities(text) {
  if (!text.includes("&")) {
    return text;
  }
  return text.replace(
    /&(#[xX][0-9a-fA-F]+|#[0-9]+|[a-zA-Z]+);/g,
    (match, body) => {
      if (body[0] === "#") {
        const code =
          body[1] === "x" || body[1] === "X"
            ? parseInt(body.slice(2), 16)
            : parseInt(body.slice(1), 10);
        return String.fromCodePoint(code);
      }
      const named = NAMED_ENTITIES[body.toLowerCase()];
      return named === undefined ? match : named;
    },
  );
}

function makeElement(tag, attrs) {
  return { tag, attrs, children: [] };
}

// Parse a start tag beginning at `html[start]` === "<". Returns
// {tag, attrs, selfClose, end} where `end` is the index just past ">", or
// null when this "<" does not begin a well-formed start tag (treated as
// text by the caller).
function matchStartTag(html, start) {
  const nameMatch = /^<([a-zA-Z][^\s/>]*)/.exec(html.slice(start));
  if (nameMatch === null) {
    return null;
  }
  const tag = nameMatch[1].toLowerCase();
  let i = start + nameMatch[0].length;
  const attrs = {};
  let selfClose = false;
  while (i < html.length) {
    while (i < html.length && /\s/.test(html[i])) {
      i += 1;
    }
    if (i >= html.length) {
      break;
    }
    if (html[i] === ">") {
      i += 1;
      return { tag, attrs, selfClose, end: i };
    }
    if (html[i] === "/") {
      selfClose = true;
      i += 1;
      continue;
    }
    let name = "";
    while (i < html.length && !/[\s/>=]/.test(html[i])) {
      name += html[i];
      i += 1;
    }
    while (i < html.length && /\s/.test(html[i])) {
      i += 1;
    }
    let value = "";
    if (html[i] === "=") {
      i += 1;
      while (i < html.length && /\s/.test(html[i])) {
        i += 1;
      }
      if (html[i] === '"' || html[i] === "'") {
        const quote = html[i];
        i += 1;
        const close = html.indexOf(quote, i);
        const stop = close === -1 ? html.length : close;
        value = decodeEntities(html.slice(i, stop));
        i = close === -1 ? html.length : close + 1;
      } else {
        let raw = "";
        while (i < html.length && !/[\s>]/.test(html[i])) {
          raw += html[i];
          i += 1;
        }
        value = decodeEntities(raw);
      }
    }
    // First occurrence wins for a duplicated attribute name; a valueless
    // attribute normalizes to "".
    if (name !== "" && !(name.toLowerCase() in attrs)) {
      attrs[name.toLowerCase()] = value;
    }
  }
  // Unterminated start tag: consume to end of input.
  return { tag, attrs, selfClose, end: html.length };
}

function indexOfCloseTag(html, tag, from) {
  const lower = html.toLowerCase();
  const needle = `</${tag}`;
  return lower.indexOf(needle, from);
}

export function parseHtml(html) {
  const root = makeElement("#root", {});
  const stack = [root];
  let i = 0;
  while (i < html.length) {
    if (html[i] !== "<") {
      const next = html.indexOf("<", i);
      const end = next === -1 ? html.length : next;
      stack[stack.length - 1].children.push(decodeEntities(html.slice(i, end)));
      i = end;
      continue;
    }
    if (html.startsWith("<!--", i)) {
      const end = html.indexOf("-->", i + 4);
      i = end === -1 ? html.length : end + 3;
      continue;
    }
    if (html.startsWith("<!", i) || html.startsWith("<?", i)) {
      const end = html.indexOf(">", i);
      i = end === -1 ? html.length : end + 1;
      continue;
    }
    if (html.startsWith("</", i)) {
      const end = html.indexOf(">", i);
      if (end === -1) {
        i = html.length;
        continue;
      }
      const name = html
        .slice(i + 2, end)
        .trim()
        .toLowerCase();
      for (let s = stack.length - 1; s > 0; s -= 1) {
        if (stack[s].tag === name) {
          stack.length = s;
          break;
        }
      }
      i = end + 1;
      continue;
    }
    const match = matchStartTag(html, i);
    if (match === null) {
      stack[stack.length - 1].children.push("<");
      i += 1;
      continue;
    }
    const element = makeElement(match.tag, match.attrs);
    stack[stack.length - 1].children.push(element);
    if (VOID_ELEMENTS.has(match.tag) || match.selfClose) {
      i = match.end;
      continue;
    }
    if (RAWTEXT_ELEMENTS.has(match.tag)) {
      const close = indexOfCloseTag(html, match.tag, match.end);
      const rawEnd = close === -1 ? html.length : close;
      const raw = html.slice(match.end, rawEnd);
      if (raw !== "") {
        element.children.push(raw);
      }
      if (close === -1) {
        i = html.length;
      } else {
        const closeEnd = html.indexOf(">", close);
        i = closeEnd === -1 ? html.length : closeEnd + 1;
      }
      continue;
    }
    stack.push(element);
    i = match.end;
  }
  return root;
}

function* iterElements(element) {
  for (const child of element.children) {
    if (typeof child !== "string") {
      yield child;
      yield* iterElements(child);
    }
  }
}

function textOf(element) {
  const parts = [];
  const walk = (node) => {
    for (const child of node.children) {
      if (typeof child === "string") {
        parts.push(child);
      } else {
        walk(child);
      }
    }
  };
  walk(element);
  return parts.join("").trim();
}

function firstByTestid(scope, testid) {
  for (const element of iterElements(scope)) {
    if (element.attrs["data-testid"] === testid) {
      return element;
    }
  }
  return null;
}

function isDigits(text) {
  return text.length > 0 && /^[0-9]+$/.test(text);
}

function findFirst(text, chars) {
  for (let index = 0; index < text.length; index += 1) {
    if (chars.includes(text[index])) {
      return index;
    }
  }
  return text.length;
}

export function removeDotSegments(path) {
  const segments = path.split("/");
  const out = [];
  for (const segment of segments) {
    if (segment === ".") {
      continue;
    }
    if (segment === "..") {
      if (out.length > 1) {
        out.pop();
      }
      continue;
    }
    out.push(segment);
  }
  const last = segments[segments.length - 1];
  if (last === "." || last === "..") {
    out.push("");
  }
  return out.join("/");
}

function splitUrl(url) {
  const colon = url.indexOf(":");
  const schemeEnd = colon === -1 ? 0 : colon + 1;
  const scheme = url.slice(0, schemeEnd);
  let rest = url.slice(schemeEnd);
  let authority = "";
  if (rest.startsWith("//")) {
    const stripped = rest.slice(2);
    const end = findFirst(stripped, "/?#");
    authority = "//" + stripped.slice(0, end);
    rest = stripped.slice(end);
  }
  const pathEnd = findFirst(rest, "?#");
  const path = rest.slice(0, pathEnd);
  const tail = rest.slice(pathEnd);
  let query = "";
  if (tail.startsWith("?")) {
    const after = tail.slice(1);
    query = after.slice(0, findFirst(after, "#"));
  }
  return { origin: scheme + authority, path, query };
}

function isAbsoluteUrl(href) {
  const colon = href.indexOf(":");
  if (colon <= 0) {
    return false;
  }
  const scheme = href.slice(0, colon);
  if (!/^[a-zA-Z][a-zA-Z0-9+.-]*$/.test(scheme)) {
    return false;
  }
  return true;
}

export function resolveUrl(base, href) {
  if (isAbsoluteUrl(href)) {
    return href;
  }
  const { origin, path: basePath, query: baseQuery } = splitUrl(base);
  if (href.startsWith("//")) {
    const colon = origin.indexOf(":");
    const scheme = colon === -1 ? "" : origin.slice(0, colon + 1);
    return scheme + href;
  }
  if (href === "" || href.startsWith("#")) {
    const query = baseQuery === "" ? "" : `?${baseQuery}`;
    return `${origin}${basePath}${query}${href}`;
  }
  if (href.startsWith("?")) {
    return `${origin}${basePath}${href}`;
  }
  const split = findFirst(href, "?#");
  const hrefPath = href.slice(0, split);
  const suffix = href.slice(split);
  let merged;
  if (hrefPath.startsWith("/")) {
    merged = hrefPath;
  } else {
    const slash = basePath.lastIndexOf("/");
    const dirEnd = slash === -1 ? 0 : slash + 1;
    merged = "/" + basePath.slice(0, dirEnd).replace(/^\/+/, "") + hrefPath;
  }
  return `${origin}${removeDotSegments(merged)}${suffix}`;
}

export function canonicalCardUrl(base, href) {
  const resolved = resolveUrl(base, href);
  const withoutFragment = resolved.slice(0, findFirst(resolved, "#"));
  const question = withoutFragment.indexOf("?");
  if (question === -1) {
    return withoutFragment;
  }
  const before = withoutFragment.slice(0, question);
  const query = withoutFragment.slice(question + 1);
  const kept = query
    .split("&")
    .filter((pair) => pair.slice(0, findFirst(pair, "=")) !== "tr");
  if (kept.length === 0) {
    return before;
  }
  return before + "?" + kept.join("&");
}

function amountInCents(dollarsText, centsText) {
  const amount = parseInt(dollarsText, 10) * 100 + parseInt(centsText, 10);
  if (amount > U32_MAX) {
    return null;
  }
  return amount;
}

function extractPrice(card) {
  const group = firstByTestid(card, "price");
  if (group === null) {
    return null;
  }
  const dollarsEl = firstByTestid(group, "price-dollars");
  const centsEl = firstByTestid(group, "price-cents");
  const perEl = firstByTestid(group, "price-per");
  if (dollarsEl === null || centsEl === null || perEl === null) {
    return null;
  }
  const dollarsText = textOf(dollarsEl);
  const centsText = textOf(centsEl);
  if (
    !isDigits(dollarsText) ||
    centsText.length !== 2 ||
    !isDigits(centsText)
  ) {
    return null;
  }
  const amount = amountInCents(dollarsText, centsText);
  if (amount === null) {
    return null;
  }
  return {
    "amount-cents": amount,
    per: textOf(perEl),
    display: `$${dollarsText}.${centsText}`,
  };
}

function extractUnitPrice(card) {
  const element = firstByTestid(card, "non-promo-unit-price");
  if (element === null) {
    return null;
  }
  const display = textOf(element);
  // "$<dollars>.<2-digit cents>/<unit>" (e.g. "$0.81/ea"); anything else --
  // promo layouts, missing decimals -- is treated as absent.
  if (!display.startsWith("$")) {
    return null;
  }
  const rest = display.slice(1);
  if (!rest.includes("/")) {
    return null;
  }
  const slash = rest.indexOf("/");
  const amountText = rest.slice(0, slash);
  const unit = rest.slice(slash + 1);
  if (!amountText.includes(".")) {
    return null;
  }
  const dot = amountText.indexOf(".");
  const dollarsText = amountText.slice(0, dot);
  const centsText = amountText.slice(dot + 1);
  if (
    !isDigits(dollarsText) ||
    centsText.length !== 2 ||
    !isDigits(centsText) ||
    unit === ""
  ) {
    return null;
  }
  const amount = amountInCents(dollarsText, centsText);
  if (amount === null) {
    return null;
  }
  return { "amount-cents": amount, unit, display };
}

function firstHref(card) {
  for (const element of iterElements(card)) {
    if (element.tag === "a" && "href" in element.attrs) {
      return element.attrs.href;
    }
  }
  return null;
}

function extractCard(card, sourceUrl) {
  // The product id comes from the data-testid on the Product element itself;
  // descendants carry product-* test ids too, so prefix-matching anywhere
  // else is wrong.
  const testid = card.attrs["data-testid"];
  if (testid === undefined || !testid.startsWith(PRODUCT_TESTID_PREFIX)) {
    return null;
  }
  const titleEl = firstByTestid(card, "product-title");
  if (titleEl === null) {
    return null;
  }
  const href = firstHref(card);
  if (href === null) {
    return null;
  }
  const subtitleEl = firstByTestid(card, "product-subtitle");
  const imageEl = firstByTestid(card, "product-image");
  const imageSrc = imageEl === null ? undefined : imageEl.attrs.src;
  return {
    "product-id": testid.slice(PRODUCT_TESTID_PREFIX.length),
    name: textOf(titleEl),
    subtitle: subtitleEl === null ? null : textOf(subtitleEl),
    url: canonicalCardUrl(sourceUrl, href),
    "image-url":
      imageSrc === undefined ? null : resolveUrl(sourceUrl, imageSrc),
    price: extractPrice(card),
    "unit-price": extractUnitPrice(card),
  };
}

function findNextPageUrl(root, sourceUrl) {
  for (const element of iterElements(root)) {
    if (element.tag !== "a") {
      continue;
    }
    const rel = element.attrs.rel;
    if (rel === undefined) {
      continue;
    }
    if (!rel.split(/\s+/).some((token) => token.toLowerCase() === "next")) {
      continue;
    }
    const href = element.attrs.href;
    if (href === undefined) {
      continue;
    }
    return resolveUrl(sourceUrl, href);
  }
  return null;
}

// Parse one New World shop-search results page into structured product-card
// data, returned as the harness-wide result envelope. See
// common/wit/html-parser.wit for the contract and docs/html-parser-plan.md
// for the pinned observable behavior.
export function parseSearchResults(html, sourceUrl) {
  const root = parseHtml(html);

  let hasContainer = false;
  for (const element of iterElements(root)) {
    if (element.attrs.id === RESULTS_CONTAINER_ID) {
      hasContainer = true;
      break;
    }
  }
  if (!hasContainer) {
    return {
      err: {
        code: NO_RESULTS_CONTAINER_CODE,
        message: NO_RESULTS_CONTAINER_MESSAGE,
      },
    };
  }

  const products = [];
  const seenUrls = new Set();
  for (const card of iterElements(root)) {
    if (card.attrs.itemtype !== PRODUCT_ITEMTYPE) {
      continue;
    }
    const product = extractCard(card, sourceUrl);
    if (product === null || seenUrls.has(product.url)) {
      continue;
    }
    seenUrls.add(product.url);
    products.push(product);
  }

  return {
    ok: {
      site: SITE,
      "source-url": sourceUrl,
      "next-page-url": findNextPageUrl(root, sourceUrl),
      products,
    },
  };
}

// ---------------------------------------------------------------------------
// Component binding glue for the `new-world-parser` world.
//
// This is the only JavaScript-binding-specific layer: it adapts the
// language-neutral envelope above to the shapes jco/componentize-js expects
// for the WIT export. Unlike Python (componentize-py `-p src` bundles a whole
// directory) and Rust (a path-dependency crate), componentize-js evaluates a
// single self-contained module and does not resolve relative imports -- so
// the core and this thin glue share one file (docs/html-parser-plan.md: core
// placement is decided per language by what the component toolchain can
// bundle). jco maps interface `new-world-product-search` to the named export
// `newWorldProductSearch`, its function `parse-search-results` to
// `parseSearchResults(html, sourceUrl)`, and WIT record fields to camelCase
// properties. For a `result<T, E>` return the guest returns the ok value and
// THROWS the error value (symmetric with the Python parser_app raising for
// err); `option<T>` none is represented as `undefined`.
// ---------------------------------------------------------------------------

function toPrice(price) {
  if (price === null) {
    return undefined;
  }
  return {
    amountCents: price["amount-cents"],
    per: price.per,
    display: price.display,
  };
}

function toUnitPrice(unitPrice) {
  if (unitPrice === null) {
    return undefined;
  }
  return {
    amountCents: unitPrice["amount-cents"],
    unit: unitPrice.unit,
    display: unitPrice.display,
  };
}

function toProductCard(product) {
  return {
    productId: product["product-id"],
    name: product.name,
    subtitle: product.subtitle === null ? undefined : product.subtitle,
    url: product.url,
    imageUrl: product["image-url"] === null ? undefined : product["image-url"],
    price: toPrice(product.price),
    unitPrice: toUnitPrice(product["unit-price"]),
  };
}

function toSearchResults(ok) {
  return {
    site: ok.site,
    sourceUrl: ok["source-url"],
    nextPageUrl: ok["next-page-url"] === null ? undefined : ok["next-page-url"],
    products: ok.products.map(toProductCard),
  };
}

export const newWorldProductSearch = {
  parseSearchResults(html, sourceUrl) {
    const envelope = parseSearchResults(html, sourceUrl);
    if (envelope.err !== undefined) {
      throw { code: envelope.err.code, message: envelope.err.message };
    }
    return toSearchResults(envelope.ok);
  },
};
