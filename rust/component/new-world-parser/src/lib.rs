//! Parsing core for the `new-world-product-search` WIT interface
//! (`common/wit/html-parser.wit`).
//!
//! One parsing core per language (docs/html-parser-plan.md): this library
//! is used directly by the host-side native tests in `tests/` and compiled
//! unchanged into `new-world-parser.wasm` through the `cfg(target_arch =
//! "wasm32")` glue at the bottom of this file -- there is never a second
//! copy of the extraction logic in this language.
//!
//! URL resolution is a small explicit RFC-3986-style resolver implemented
//! identically in all three language cores (rather than each language's URL
//! library) so canonical URLs -- and therefore deduplication keys -- are
//! byte-identical across implementations.

use scraper::{ElementRef, Html, Selector};

/// A price as displayed on a product card.
#[derive(Debug, PartialEq, Eq)]
pub struct Price {
    /// Whole price in cents (e.g. $9.73 -> 973).
    pub amount_cents: u32,
    /// The per-unit designator shown with the price (e.g. "ea").
    pub per: String,
    /// Raw display text, for provenance (e.g. "$9.73").
    pub display: String,
}

/// A comparative unit price (e.g. "$0.81/ea").
#[derive(Debug, PartialEq, Eq)]
pub struct UnitPrice {
    pub amount_cents: u32,
    pub unit: String,
    pub display: String,
}

/// One product card extracted from a search-results page.
#[derive(Debug, PartialEq, Eq)]
pub struct ProductCard {
    pub product_id: String,
    pub name: String,
    pub subtitle: Option<String>,
    pub url: String,
    pub image_url: Option<String>,
    pub price: Option<Price>,
    pub unit_price: Option<UnitPrice>,
}

/// Structured product-card data parsed from one search-results page.
#[derive(Debug, PartialEq, Eq)]
pub struct SearchResults {
    pub site: String,
    pub source_url: String,
    pub next_page_url: Option<String>,
    pub products: Vec<ProductCard>,
}

/// A structured parse failure.
#[derive(Debug, PartialEq, Eq)]
pub struct ParseError {
    /// Stable kebab-case error code (e.g. "no-results-container").
    pub code: String,
    pub message: String,
}

const SITE: &str = "new-world";
const PRODUCT_ITEMTYPE: &str = "https://schema.org/Product";
const PRODUCT_TESTID_PREFIX: &str = "product-";

/// The element that makes a document recognizable as a search-results page.
/// The captured New World page wraps its results section in `id="search"`;
/// a document without it yields `err(no-results-container)`, while a page
/// with the container but zero product cards is `ok` with empty `products`.
const RESULTS_CONTAINER_SELECTOR: &str = "#search";
const NO_RESULTS_CONTAINER_CODE: &str = "no-results-container";
const NO_RESULTS_CONTAINER_MESSAGE: &str =
    "no search results container (id=\"search\") in document";

fn selector(css: &str) -> Selector {
    Selector::parse(css).expect("static selector must parse")
}

fn is_digits(text: &str) -> bool {
    !text.is_empty() && text.chars().all(|c| c.is_ascii_digit())
}

fn element_text(el: ElementRef) -> String {
    el.text().collect::<String>().trim().to_string()
}

fn first_descendant<'a>(card: ElementRef<'a>, css: &str) -> Option<ElementRef<'a>> {
    card.select(&selector(css)).next()
}

/// Remove `.` and `..` segments from an absolute URL path (RFC 3986
/// section 5.2.4, simplified for already-merged paths).
pub fn remove_dot_segments(path: &str) -> String {
    let segments: Vec<&str> = path.split('/').collect();
    let mut out: Vec<&str> = Vec::new();
    for segment in &segments {
        match *segment {
            "." => {}
            ".." => {
                if out.len() > 1 {
                    out.pop();
                }
            }
            other => out.push(other),
        }
    }
    if matches!(segments.last(), Some(&".") | Some(&"..")) {
        out.push("");
    }
    out.join("/")
}

/// Split `url` into `(origin, path, query)` where `origin` is
/// `scheme://authority` (or just `scheme:` for a URL without an authority),
/// `path` excludes the query/fragment, and `query` excludes its leading `?`.
fn split_url(url: &str) -> (String, String, String) {
    let scheme_end = url.find(':').map(|i| i + 1).unwrap_or(0);
    let (scheme, rest) = url.split_at(scheme_end);
    let (authority, rest) = if let Some(stripped) = rest.strip_prefix("//") {
        let end = stripped.find(['/', '?', '#']).unwrap_or(stripped.len());
        (format!("//{}", &stripped[..end]), &stripped[end..])
    } else {
        (String::new(), rest)
    };
    let path_end = rest.find(['?', '#']).unwrap_or(rest.len());
    let (path, tail) = rest.split_at(path_end);
    let query = match tail.strip_prefix('?') {
        Some(after) => after[..after.find('#').unwrap_or(after.len())].to_string(),
        None => String::new(),
    };
    (format!("{scheme}{authority}"), path.to_string(), query)
}

fn is_absolute_url(href: &str) -> bool {
    let Some(colon) = href.find(':') else {
        return false;
    };
    let scheme = &href[..colon];
    let mut chars = scheme.chars();
    match chars.next() {
        Some(first) if first.is_ascii_alphabetic() => {
            chars.all(|c| c.is_ascii_alphanumeric() || matches!(c, '+' | '.' | '-'))
        }
        _ => false,
    }
}

/// Resolve `href` against the absolute `base` URL. A deliberately small
/// RFC-3986-style resolver, implemented identically in every language core
/// so canonical URLs match byte-for-byte across implementations.
pub fn resolve_url(base: &str, href: &str) -> String {
    if is_absolute_url(href) {
        return href.to_string();
    }
    let (origin, base_path, base_query) = split_url(base);
    if let Some(rest) = href.strip_prefix("//") {
        let scheme = &origin[..origin.find(':').map(|i| i + 1).unwrap_or(0)];
        return format!("{scheme}//{rest}");
    }
    if href.is_empty() || href.starts_with('#') {
        let query = if base_query.is_empty() {
            String::new()
        } else {
            format!("?{base_query}")
        };
        return format!("{origin}{base_path}{query}{href}");
    }
    if href.starts_with('?') {
        return format!("{origin}{base_path}{href}");
    }
    let split = href.find(['?', '#']).unwrap_or(href.len());
    let (href_path, suffix) = href.split_at(split);
    let merged = if href_path.starts_with('/') {
        href_path.to_string()
    } else {
        let dir_end = base_path.rfind('/').map(|i| i + 1).unwrap_or(0);
        format!(
            "/{}{href_path}",
            &base_path[..dir_end].trim_start_matches('/')
        )
    };
    format!("{origin}{}{suffix}", remove_dot_segments(&merged))
}

/// Canonicalize a product-card link: resolve against `base`, drop any
/// fragment, drop the volatile `tr` query parameter, and keep every other
/// query parameter exactly as found.
pub fn canonical_card_url(base: &str, href: &str) -> String {
    let resolved = resolve_url(base, href);
    let without_fragment = &resolved[..resolved.find('#').unwrap_or(resolved.len())];
    let Some(question) = without_fragment.find('?') else {
        return without_fragment.to_string();
    };
    let (before, query) = without_fragment.split_at(question);
    let kept: Vec<&str> = query[1..]
        .split('&')
        .filter(|pair| {
            let key = &pair[..pair.find('=').unwrap_or(pair.len())];
            key != "tr"
        })
        .collect();
    if kept.is_empty() {
        before.to_string()
    } else {
        format!("{before}?{}", kept.join("&"))
    }
}

/// Sum an already-digits-checked two-digit cents string. Kept free of
/// fallible parsing: a two-ASCII-digit number can never overflow `u32`.
fn two_digit_cents(cents_text: &str) -> u32 {
    cents_text
        .bytes()
        .fold(0u32, |acc, digit| acc * 10 + u32::from(digit - b'0'))
}

/// `dollars * 100 + cents` in cents, or `None` if the dollars text does not
/// fit in `u32` or the total overflows `u32` (the WIT `amount-cents` type).
fn amount_in_cents(dollars_text: &str, cents: u32) -> Option<u32> {
    let dollars: u32 = dollars_text.parse().ok()?;
    dollars.checked_mul(100)?.checked_add(cents)
}

fn extract_price(card: ElementRef) -> Option<Price> {
    let group = first_descendant(card, "[data-testid=\"price\"]")?;
    let dollars_text = element_text(first_descendant(group, "[data-testid=\"price-dollars\"]")?);
    let cents_text = element_text(first_descendant(group, "[data-testid=\"price-cents\"]")?);
    let per = element_text(first_descendant(group, "[data-testid=\"price-per\"]")?);
    if !is_digits(&dollars_text) || cents_text.len() != 2 || !is_digits(&cents_text) {
        return None;
    }
    let amount_cents = amount_in_cents(&dollars_text, two_digit_cents(&cents_text))?;
    Some(Price {
        amount_cents,
        per,
        display: format!("${dollars_text}.{cents_text}"),
    })
}

fn extract_unit_price(card: ElementRef) -> Option<UnitPrice> {
    let el = first_descendant(card, "[data-testid=\"non-promo-unit-price\"]")?;
    let display = element_text(el);
    // "$<dollars>.<2-digit cents>/<unit>" (e.g. "$0.81/ea"); anything else
    // -- promo layouts, missing decimals -- is treated as absent.
    let rest = display.strip_prefix('$')?;
    let (amount_text, unit) = rest.split_once('/')?;
    let (dollars_text, cents_text) = amount_text.split_once('.')?;
    if !is_digits(dollars_text)
        || cents_text.len() != 2
        || !is_digits(cents_text)
        || unit.is_empty()
    {
        return None;
    }
    let amount_cents = amount_in_cents(dollars_text, two_digit_cents(cents_text))?;
    Some(UnitPrice {
        amount_cents,
        unit: unit.to_string(),
        display,
    })
}

fn extract_card(card: ElementRef, source_url: &str) -> Option<ProductCard> {
    // The product id comes from the data-testid on the Product element
    // itself; descendants carry product-* test ids too, so prefix-matching
    // anywhere else is wrong.
    let testid = card.value().attr("data-testid")?;
    let product_id = testid.strip_prefix(PRODUCT_TESTID_PREFIX)?;
    let name = element_text(first_descendant(card, "[data-testid=\"product-title\"]")?);
    let href = first_descendant(card, "a[href]").and_then(|link| link.value().attr("href"))?;
    let url = canonical_card_url(source_url, href);
    let subtitle = first_descendant(card, "[data-testid=\"product-subtitle\"]").map(element_text);
    let image_url = first_descendant(card, "[data-testid=\"product-image\"]")
        .and_then(|el| el.value().attr("src"))
        .map(|src| resolve_url(source_url, src));
    Some(ProductCard {
        product_id: product_id.to_string(),
        name,
        subtitle,
        url,
        image_url,
        price: extract_price(card),
        unit_price: extract_unit_price(card),
    })
}

fn find_next_page_url(document: &Html, source_url: &str) -> Option<String> {
    for anchor in document.select(&selector("a")) {
        let Some(rel) = anchor.value().attr("rel") else {
            continue;
        };
        let has_next_rel = rel
            .split_ascii_whitespace()
            .any(|token| token.eq_ignore_ascii_case("next"));
        if !has_next_rel {
            continue;
        }
        let Some(href) = anchor.value().attr("href") else {
            continue;
        };
        return Some(resolve_url(source_url, href));
    }
    None
}

/// Parse one New World shop-search results page into structured
/// product-card data. See `common/wit/html-parser.wit` for the contract and
/// docs/html-parser-plan.md for the pinned observable behavior.
pub fn parse_search_results(html: &str, source_url: &str) -> Result<SearchResults, ParseError> {
    let document = Html::parse_document(html);

    if document
        .select(&selector(RESULTS_CONTAINER_SELECTOR))
        .next()
        .is_none()
    {
        return Err(ParseError {
            code: NO_RESULTS_CONTAINER_CODE.to_string(),
            message: NO_RESULTS_CONTAINER_MESSAGE.to_string(),
        });
    }

    let mut products: Vec<ProductCard> = Vec::new();
    let mut seen_urls: Vec<String> = Vec::new();
    let product_selector = selector(&format!("[itemtype=\"{PRODUCT_ITEMTYPE}\"]"));
    for card in document.select(&product_selector) {
        let Some(product) = extract_card(card, source_url) else {
            continue;
        };
        if seen_urls.contains(&product.url) {
            continue;
        }
        seen_urls.push(product.url.clone());
        products.push(product);
    }

    Ok(SearchResults {
        site: SITE.to_string(),
        source_url: source_url.to_string(),
        next_page_url: find_next_page_url(&document, source_url),
        products,
    })
}

#[cfg(target_arch = "wasm32")]
mod bindings;

#[cfg(target_arch = "wasm32")]
mod wasm {
    use crate::bindings::exports::common::html_parser::new_world_product_search::{
        Guest, ParseError as WitParseError, Price as WitPrice, ProductCard as WitProductCard,
        SearchResults as WitSearchResults, UnitPrice as WitUnitPrice,
    };

    struct Component;

    fn to_wit_price(price: crate::Price) -> WitPrice {
        WitPrice {
            amount_cents: price.amount_cents,
            per: price.per,
            display: price.display,
        }
    }

    fn to_wit_unit_price(unit_price: crate::UnitPrice) -> WitUnitPrice {
        WitUnitPrice {
            amount_cents: unit_price.amount_cents,
            unit: unit_price.unit,
            display: unit_price.display,
        }
    }

    fn to_wit_card(card: crate::ProductCard) -> WitProductCard {
        WitProductCard {
            product_id: card.product_id,
            name: card.name,
            subtitle: card.subtitle,
            url: card.url,
            image_url: card.image_url,
            price: card.price.map(to_wit_price),
            unit_price: card.unit_price.map(to_wit_unit_price),
        }
    }

    impl Guest for Component {
        fn parse_search_results(
            html: String,
            source_url: String,
        ) -> Result<WitSearchResults, WitParseError> {
            match crate::parse_search_results(&html, &source_url) {
                Ok(results) => Ok(WitSearchResults {
                    site: results.site,
                    source_url: results.source_url,
                    next_page_url: results.next_page_url,
                    products: results.products.into_iter().map(to_wit_card).collect(),
                }),
                Err(error) => Err(WitParseError {
                    code: error.code,
                    message: error.message,
                }),
            }
        }
    }

    crate::bindings::export!(Component with_types_in crate::bindings);
}
