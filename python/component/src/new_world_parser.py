"""Parsing core for the ``new-world-product-search`` WIT interface
(``common/wit/html-parser.wit``).

One parsing core per language (docs/html-parser-plan.md): this module is
used directly by the host-side native tests in ``tests/`` and compiled
unchanged into ``new-world-parser.wasm`` through the thin component glue in
``parser_app.py`` -- there is never a second copy of the extraction logic
in this language.

The HTML tree is built with the stdlib ``html.parser`` tokenizer only
(componentize-py bundles the stdlib; constitution section 6.3 -- no
third-party parser dependency). ``parse_search_results`` returns the
harness-wide result envelope directly -- ``{"ok": {...}}`` or
``{"err": {...}}`` -- with every record as a plain dict keyed exactly like
the JSON contract (kebab-case, ``None`` for an absent WIT ``option<>``).

URL resolution is a small explicit RFC-3986-style resolver implemented
identically in all three language cores (rather than each language's URL
library) so canonical URLs -- and therefore deduplication keys -- are
byte-identical across implementations.
"""

from __future__ import annotations

from html.parser import HTMLParser

_SITE = "new-world"
_PRODUCT_ITEMTYPE = "https://schema.org/Product"
_PRODUCT_TESTID_PREFIX = "product-"
_U32_MAX = 4294967295

# The element that makes a document recognizable as a search-results page.
# The captured New World page wraps its results section in id="search"; a
# document without it yields err(no-results-container), while a page with
# the container but zero product cards is ok with empty products.
_RESULTS_CONTAINER_ID = "search"
_NO_RESULTS_CONTAINER_CODE = "no-results-container"
_NO_RESULTS_CONTAINER_MESSAGE = 'no search results container (id="search") in document'

# HTML void elements never take a closing tag and must not be pushed onto
# the open-element stack (mirrors the html5ever behavior the Rust core gets
# for free).
_VOID_ELEMENTS = frozenset(
    {
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
    }
)


class _Element:
    """One element node in the tolerant tree; children mix ``_Element`` and
    ``str`` (text) nodes."""

    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: dict[str, str]):
        self.tag = tag
        self.attrs = attrs
        self.children: list[_Element | str] = []


class _TreeBuilder(HTMLParser):
    """Tolerant tree builder over the stdlib tokenizer: void elements are
    never pushed, a close tag pops to its nearest matching open tag, and an
    unmatched close tag is ignored."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Element("#root", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # First occurrence wins for duplicated attribute names (html5ever
        # behavior); a valueless attribute normalizes to "".
        attr_dict: dict[str, str] = {}
        for name, value in attrs:
            if name not in attr_dict:
                attr_dict[name] = value if value is not None else ""
        element = _Element(tag, attr_dict)
        self._stack[-1].children.append(element)
        if tag not in _VOID_ELEMENTS:
            self._stack.append(element)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


def _parse_html(html: str) -> _Element:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


def _iter_elements(element: _Element):
    """Every descendant element of ``element``, in document (DFS) order."""
    for child in element.children:
        if isinstance(child, _Element):
            yield child
            yield from _iter_elements(child)


def _text(element: _Element) -> str:
    """Concatenated descendant text, trimmed."""
    parts: list[str] = []

    def walk(node: _Element) -> None:
        for child in node.children:
            if isinstance(child, _Element):
                walk(child)
            else:
                parts.append(child)

    walk(element)
    return "".join(parts).strip()


def _first_by_testid(scope: _Element, testid: str) -> _Element | None:
    for element in _iter_elements(scope):
        if element.attrs.get("data-testid") == testid:
            return element
    return None


def _is_digits(text: str) -> bool:
    return bool(text) and all(char in "0123456789" for char in text)


def _find_first(text: str, chars: str) -> int:
    """Index of the first occurrence of any of ``chars``, else ``len(text)``."""
    for index, char in enumerate(text):
        if char in chars:
            return index
    return len(text)


def remove_dot_segments(path: str) -> str:
    """Remove ``.`` and ``..`` segments from an absolute URL path (RFC 3986
    section 5.2.4, simplified for already-merged paths)."""
    segments = path.split("/")
    out: list[str] = []
    for segment in segments:
        if segment == ".":
            continue
        if segment == "..":
            if len(out) > 1:
                out.pop()
            continue
        out.append(segment)
    if segments[-1] in (".", ".."):
        out.append("")
    return "/".join(out)


def _split_url(url: str) -> tuple[str, str, str]:
    """Split ``url`` into ``(origin, path, query)`` where ``origin`` is
    ``scheme://authority`` (or just ``scheme:`` for a URL without an
    authority), ``path`` excludes the query/fragment, and ``query`` excludes
    its leading ``?``."""
    colon = url.find(":")
    scheme_end = colon + 1 if colon != -1 else 0
    scheme, rest = url[:scheme_end], url[scheme_end:]
    authority = ""
    if rest.startswith("//"):
        stripped = rest[2:]
        end = _find_first(stripped, "/?#")
        authority = "//" + stripped[:end]
        rest = stripped[end:]
    path_end = _find_first(rest, "?#")
    path, tail = rest[:path_end], rest[path_end:]
    query = ""
    if tail.startswith("?"):
        after = tail[1:]
        query = after[: _find_first(after, "#")]
    return scheme + authority, path, query


def _is_absolute_url(href: str) -> bool:
    colon = href.find(":")
    if colon == -1:
        return False
    scheme = href[:colon]
    if not scheme:
        return False
    first, rest = scheme[0], scheme[1:]
    if not (first.isascii() and first.isalpha()):
        return False
    return all((char.isascii() and char.isalnum()) or char in "+.-" for char in rest)


def resolve_url(base: str, href: str) -> str:
    """Resolve ``href`` against the absolute ``base`` URL. A deliberately
    small RFC-3986-style resolver, implemented identically in every language
    core so canonical URLs match byte-for-byte across implementations."""
    if _is_absolute_url(href):
        return href
    origin, base_path, base_query = _split_url(base)
    if href.startswith("//"):
        colon = origin.find(":")
        scheme = origin[: colon + 1] if colon != -1 else ""
        return scheme + href
    if href == "" or href.startswith("#"):
        query = f"?{base_query}" if base_query else ""
        return f"{origin}{base_path}{query}{href}"
    if href.startswith("?"):
        return f"{origin}{base_path}{href}"
    split = _find_first(href, "?#")
    href_path, suffix = href[:split], href[split:]
    if href_path.startswith("/"):
        merged = href_path
    else:
        slash = base_path.rfind("/")
        dir_end = slash + 1 if slash != -1 else 0
        merged = "/" + base_path[:dir_end].lstrip("/") + href_path
    return f"{origin}{remove_dot_segments(merged)}{suffix}"


def canonical_card_url(base: str, href: str) -> str:
    """Canonicalize a product-card link: resolve against ``base``, drop any
    fragment, drop the volatile ``tr`` query parameter, and keep every other
    query parameter exactly as found."""
    resolved = resolve_url(base, href)
    without_fragment = resolved[: _find_first(resolved, "#")]
    question = without_fragment.find("?")
    if question == -1:
        return without_fragment
    before, query = without_fragment[:question], without_fragment[question + 1 :]
    kept = [pair for pair in query.split("&") if pair[: _find_first(pair, "=")] != "tr"]
    if not kept:
        return before
    return before + "?" + "&".join(kept)


def _amount_in_cents(dollars_text: str, cents_text: str) -> int | None:
    """``dollars * 100 + cents`` in cents, or ``None`` when the total does
    not fit the WIT ``amount-cents`` type (u32)."""
    amount = int(dollars_text) * 100 + int(cents_text)
    if amount > _U32_MAX:
        return None
    return amount


def _extract_price(card: _Element) -> dict | None:
    group = _first_by_testid(card, "price")
    if group is None:
        return None
    dollars_el = _first_by_testid(group, "price-dollars")
    cents_el = _first_by_testid(group, "price-cents")
    per_el = _first_by_testid(group, "price-per")
    if dollars_el is None or cents_el is None or per_el is None:
        return None
    dollars_text, cents_text = _text(dollars_el), _text(cents_el)
    if (
        not _is_digits(dollars_text)
        or len(cents_text) != 2
        or not _is_digits(cents_text)
    ):
        return None
    amount = _amount_in_cents(dollars_text, cents_text)
    if amount is None:
        return None
    return {
        "amount-cents": amount,
        "per": _text(per_el),
        "display": f"${dollars_text}.{cents_text}",
    }


def _extract_unit_price(card: _Element) -> dict | None:
    element = _first_by_testid(card, "non-promo-unit-price")
    if element is None:
        return None
    display = _text(element)
    # "$<dollars>.<2-digit cents>/<unit>" (e.g. "$0.81/ea"); anything else
    # -- promo layouts, missing decimals -- is treated as absent.
    if not display.startswith("$"):
        return None
    rest = display[1:]
    if "/" not in rest:
        return None
    amount_text, _, unit = rest.partition("/")
    if "." not in amount_text:
        return None
    dollars_text, _, cents_text = amount_text.partition(".")
    if (
        not _is_digits(dollars_text)
        or len(cents_text) != 2
        or not _is_digits(cents_text)
        or not unit
    ):
        return None
    amount = _amount_in_cents(dollars_text, cents_text)
    if amount is None:
        return None
    return {"amount-cents": amount, "unit": unit, "display": display}


def _extract_card(card: _Element, source_url: str) -> dict | None:
    # The product id comes from the data-testid on the Product element
    # itself; descendants carry product-* test ids too, so prefix-matching
    # anywhere else is wrong.
    testid = card.attrs.get("data-testid")
    if testid is None or not testid.startswith(_PRODUCT_TESTID_PREFIX):
        return None
    title_el = _first_by_testid(card, "product-title")
    if title_el is None:
        return None
    href = next(
        (
            element.attrs["href"]
            for element in _iter_elements(card)
            if element.tag == "a" and "href" in element.attrs
        ),
        None,
    )
    if href is None:
        return None
    subtitle_el = _first_by_testid(card, "product-subtitle")
    image_el = _first_by_testid(card, "product-image")
    image_src = image_el.attrs.get("src") if image_el is not None else None
    return {
        "product-id": testid[len(_PRODUCT_TESTID_PREFIX) :],
        "name": _text(title_el),
        "subtitle": _text(subtitle_el) if subtitle_el is not None else None,
        "url": canonical_card_url(source_url, href),
        "image-url": resolve_url(source_url, image_src)
        if image_src is not None
        else None,
        "price": _extract_price(card),
        "unit-price": _extract_unit_price(card),
    }


def _find_next_page_url(root: _Element, source_url: str) -> str | None:
    for element in _iter_elements(root):
        if element.tag != "a":
            continue
        rel = element.attrs.get("rel")
        if rel is None:
            continue
        if not any(token.lower() == "next" for token in rel.split()):
            continue
        href = element.attrs.get("href")
        if href is None:
            continue
        return resolve_url(source_url, href)
    return None


def parse_search_results(html: str, source_url: str) -> dict:
    """Parse one New World shop-search results page into structured
    product-card data, returned as the harness-wide result envelope. See
    ``common/wit/html-parser.wit`` for the contract and
    docs/html-parser-plan.md for the pinned observable behavior."""
    root = _parse_html(html)

    if not any(
        element.attrs.get("id") == _RESULTS_CONTAINER_ID
        for element in _iter_elements(root)
    ):
        return {
            "err": {
                "code": _NO_RESULTS_CONTAINER_CODE,
                "message": _NO_RESULTS_CONTAINER_MESSAGE,
            }
        }

    products: list[dict] = []
    seen_urls: set[str] = set()
    for card in _iter_elements(root):
        if card.attrs.get("itemtype") != _PRODUCT_ITEMTYPE:
            continue
        product = _extract_card(card, source_url)
        if product is None or product["url"] in seen_urls:
            continue
        seen_urls.add(product["url"])
        products.append(product)

    return {
        "ok": {
            "site": _SITE,
            "source-url": source_url,
            "next-page-url": _find_next_page_url(root, source_url),
            "products": products,
        }
    }
