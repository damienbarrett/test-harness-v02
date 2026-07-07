//! Host-side native tests for the New World search-results parsing core.
//!
//! The first test drives the SAME declarative case the central WASM harness
//! runs (`common/functions/new-world-product-search/parse-search-results.
//! test.json`), resolving its `$fixture` descriptor through the thin fixture
//! adapter below and deep-comparing the core's output against the case's
//! expected result envelope. No schema validation happens here --
//! `contracts:check` owns schema conformance (docs/html-parser-plan.md).
//!
//! The remaining tests pin the parsing core's edge behavior with focused
//! inline HTML fragments, and pin the adapter's error paths against the
//! canonical conformance case list in
//! `test-harness/tests/fixture_conformance.py` (case names are mirrored
//! with `_` for `-`, Rust identifiers not allowing dashes: missing-file,
//! path-is-a-directory, corrupt-gzip, non-utf8-bytes, dotdot-traversal,
//! oversized-on-disk, gzip-decompressed-oversized) so drift between the
//! languages' adapters stays grep-detectable.

use std::error::Error;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

use new_world_parser::{
    canonical_card_url, parse_search_results, remove_dot_segments, resolve_url, SearchResults,
};
use serde_json::{json, Value};

type TestResult<T = ()> = Result<T, Box<dyn Error>>;

// ---------------------------------------------------------------------------
// Thin fixture adapter: gzip + utf-8 + containment under common/fixtures/
// only (mirrors the harness contract in test-harness/src/harness/fixtures.py
// for the subset a native suite needs).
// ---------------------------------------------------------------------------

const DEFAULT_MAX_BYTES: usize = 8 * 1024 * 1024;

fn resolve_fixture(descriptor: &Value, root: &Path, max_bytes: usize) -> Result<String, String> {
    let fixture_ref = descriptor["$fixture"]
        .as_str()
        .ok_or_else(|| "'$fixture' must be a string repo-root-relative path".to_string())?;

    let compression = match &descriptor["compression"] {
        Value::Null => None,
        Value::String(value) if value == "gzip" => Some("gzip"),
        other => return Err(format!("unsupported compression {other}")),
    };
    match &descriptor["encoding"] {
        Value::Null => {}
        Value::String(value) if value == "utf-8" => {}
        other => return Err(format!("unsupported encoding {other}")),
    }

    if Path::new(fixture_ref).is_absolute() {
        return Err(format!(
            "fixture '{fixture_ref}' must be a repo-root-relative path, not an absolute path"
        ));
    }

    // `root` is expected to be canonical (the repo root / a canonicalized
    // temp tree); canonicalizing the joined path then resolves both `..`
    // traversal and symlink escapes before the containment check.
    let canonical = root.join(fixture_ref).canonicalize().map_err(|_| {
        format!("fixture '{fixture_ref}' does not exist (or is not a regular file)")
    })?;
    if !canonical.starts_with(root.join("common").join("fixtures")) {
        return Err(format!(
            "fixture '{fixture_ref}' must resolve under common/fixtures/"
        ));
    }

    let data = fs::read(&canonical).map_err(|_| {
        format!("fixture '{fixture_ref}' does not exist (or is not a regular file)")
    })?;
    if data.len() > max_bytes {
        return Err(format!(
            "fixture '{fixture_ref}' is {} bytes on disk, which exceeds the {max_bytes}-byte limit",
            data.len()
        ));
    }

    let data = if compression == Some("gzip") {
        let mut decoded: Vec<u8> = Vec::new();
        flate2::read::GzDecoder::new(data.as_slice())
            .take(max_bytes as u64 + 1)
            .read_to_end(&mut decoded)
            .map_err(|e| format!("fixture '{fixture_ref}' is not valid gzip data: {e}"))?;
        if decoded.len() > max_bytes {
            return Err(format!(
                "fixture '{fixture_ref}' decompresses to more than {max_bytes} bytes"
            ));
        }
        decoded
    } else {
        data
    };

    String::from_utf8(data).map_err(|_| format!("fixture '{fixture_ref}' is not valid utf-8"))
}

// ---------------------------------------------------------------------------
// Shared-suite execution: the one captured-page case, via the adapter.
// ---------------------------------------------------------------------------

fn repo_root() -> PathBuf {
    // new-world-parser -> component -> rust -> repo root; canonicalized so
    // the adapter's containment check compares canonical paths.
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("..")
        .canonicalize()
        .expect("repo root exists")
}

fn load_suite() -> TestResult<Value> {
    let path = repo_root()
        .join("common")
        .join("functions")
        .join("new-world-product-search")
        .join("parse-search-results.test.json");
    Ok(serde_json::from_str(&fs::read_to_string(path)?)?)
}

fn card_to_json(card: &new_world_parser::ProductCard) -> Value {
    json!({
        "product-id": card.product_id,
        "name": card.name,
        "subtitle": card.subtitle,
        "url": card.url,
        "image-url": card.image_url,
        "price": card.price.as_ref().map(|price| json!({
            "amount-cents": price.amount_cents,
            "per": price.per,
            "display": price.display,
        })),
        "unit-price": card.unit_price.as_ref().map(|unit_price| json!({
            "amount-cents": unit_price.amount_cents,
            "unit": unit_price.unit,
            "display": unit_price.display,
        })),
    })
}

/// The core's result as the harness-wide `{"ok": ...}`/`{"err": ...}`
/// envelope, in the exact JSON shape the suite's `expected` uses.
fn envelope_to_json(result: &Result<SearchResults, new_world_parser::ParseError>) -> Value {
    match result {
        Ok(results) => json!({
            "ok": {
                "site": results.site,
                "source-url": results.source_url,
                "next-page-url": results.next_page_url,
                "products": results.products.iter().map(card_to_json).collect::<Vec<_>>(),
            }
        }),
        Err(error) => json!({
            "err": { "code": error.code, "message": error.message }
        }),
    }
}

#[test]
fn shared_suite_case_matches_expected_envelope() -> TestResult {
    let suite = load_suite()?;
    let root = repo_root();
    for case in suite["tests"].as_array().expect("suite has tests") {
        let html = resolve_fixture(&case["input"]["html"], &root, DEFAULT_MAX_BYTES)?;
        let source_url = case["input"]["source-url"].as_str().expect("source-url");
        let actual = envelope_to_json(&parse_search_results(&html, source_url));
        assert_eq!(
            actual, case["expected"],
            "case '{}' diverged",
            case["description"]
        );
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Fixture adapter error paths (canonical conformance case names).
// ---------------------------------------------------------------------------

fn temp_root(tag: &str) -> PathBuf {
    let root = std::env::temp_dir().join(format!("nwp-adapter-{}-{tag}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("common").join("fixtures").join("html-parser"))
        .expect("create temp fixture tree");
    root.canonicalize().expect("canonical temp root")
}

fn descriptor(path: &str, compression: Option<&str>) -> Value {
    match compression {
        Some(value) => json!({ "$fixture": path, "compression": value }),
        None => json!({ "$fixture": path }),
    }
}

fn gzip_bytes(data: &[u8]) -> Vec<u8> {
    use std::io::Write;
    let mut encoder = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
    encoder.write_all(data).expect("gzip write");
    encoder.finish().expect("gzip finish")
}

#[test]
fn adapter_happy_path_gzip_and_plain() {
    let root = temp_root("happy");
    fs::write(
        root.join("common/fixtures/html-parser/sample.html"),
        "<html>plain</html>",
    )
    .expect("write");
    fs::write(
        root.join("common/fixtures/html-parser/page.html.gz"),
        gzip_bytes("<html>gzipped</html>".as_bytes()),
    )
    .expect("write");
    assert_eq!(
        resolve_fixture(
            &descriptor("common/fixtures/html-parser/sample.html", None),
            &root,
            DEFAULT_MAX_BYTES
        ),
        Ok("<html>plain</html>".to_string())
    );
    assert_eq!(
        resolve_fixture(
            &json!({
                "$fixture": "common/fixtures/html-parser/page.html.gz",
                "compression": "gzip",
                "encoding": "utf-8",
            }),
            &root,
            DEFAULT_MAX_BYTES
        ),
        Ok("<html>gzipped</html>".to_string())
    );
}

#[test]
fn adapter_missing_file() {
    // conformance case: missing-file
    let root = temp_root("missing-file");
    let err = resolve_fixture(
        &descriptor("common/fixtures/html-parser/missing.html", None),
        &root,
        DEFAULT_MAX_BYTES,
    )
    .unwrap_err();
    assert!(err.contains("does not exist"), "{err}");
}

#[test]
fn adapter_path_is_a_directory() {
    // conformance case: path-is-a-directory
    let root = temp_root("directory");
    let err = resolve_fixture(
        &descriptor("common/fixtures/html-parser", None),
        &root,
        DEFAULT_MAX_BYTES,
    )
    .unwrap_err();
    assert!(err.contains("does not exist"), "{err}");
}

#[test]
fn adapter_corrupt_gzip() {
    // conformance case: corrupt-gzip
    let root = temp_root("corrupt-gzip");
    fs::write(
        root.join("common/fixtures/html-parser/corrupt.html.gz"),
        "this is not gzip data at all",
    )
    .expect("write");
    let err = resolve_fixture(
        &descriptor("common/fixtures/html-parser/corrupt.html.gz", Some("gzip")),
        &root,
        DEFAULT_MAX_BYTES,
    )
    .unwrap_err();
    assert!(err.contains("not valid gzip data"), "{err}");
}

#[test]
fn adapter_non_utf8_bytes() {
    // conformance case: non-utf8-bytes
    let root = temp_root("non-utf8");
    fs::write(
        root.join("common/fixtures/html-parser/latin1.html"),
        [0x63, 0x61, 0x66, 0xE9], // "café" in latin-1
    )
    .expect("write");
    let err = resolve_fixture(
        &descriptor("common/fixtures/html-parser/latin1.html", None),
        &root,
        DEFAULT_MAX_BYTES,
    )
    .unwrap_err();
    assert!(err.contains("not valid utf-8"), "{err}");
}

#[test]
fn adapter_dotdot_traversal() {
    // conformance case: dotdot-traversal
    let root = temp_root("traversal");
    fs::write(root.join("secret.txt"), "top secret").expect("write");
    let err = resolve_fixture(
        &descriptor("common/fixtures/../../secret.txt", None),
        &root,
        DEFAULT_MAX_BYTES,
    )
    .unwrap_err();
    assert!(err.contains("must resolve under common/fixtures/"), "{err}");
}

#[test]
fn adapter_absolute_path() {
    // conformance case: absolute-path
    let root = temp_root("absolute");
    let err =
        resolve_fixture(&descriptor("/etc/hostname", None), &root, DEFAULT_MAX_BYTES).unwrap_err();
    assert!(err.contains("must be a repo-root-relative path"), "{err}");
}

#[test]
fn adapter_oversized_on_disk() {
    // conformance case: oversized-on-disk
    let root = temp_root("oversized");
    fs::write(
        root.join("common/fixtures/html-parser/big.html"),
        vec![b'x'; 64],
    )
    .expect("write");
    let err = resolve_fixture(
        &descriptor("common/fixtures/html-parser/big.html", None),
        &root,
        16,
    )
    .unwrap_err();
    assert!(err.contains("is 64 bytes on disk"), "{err}");
}

#[test]
fn adapter_gzip_decompressed_oversized() {
    // conformance case: gzip-decompressed-oversized
    let root = temp_root("gzip-bomb");
    fs::write(
        root.join("common/fixtures/html-parser/bomb.html.gz"),
        gzip_bytes(&vec![0u8; 262144]),
    )
    .expect("write");
    let err = resolve_fixture(
        &descriptor("common/fixtures/html-parser/bomb.html.gz", Some("gzip")),
        &root,
        1024,
    )
    .unwrap_err();
    assert!(
        err.contains("decompresses to more than 1024 bytes"),
        "{err}"
    );
}

#[test]
fn adapter_rejects_malformed_descriptors() {
    // conformance cases: non-string-fixture-path, unsupported-compression-value,
    // unsupported-encoding-value
    let root = temp_root("descriptor-shape");
    let err = resolve_fixture(&json!({ "$fixture": 42 }), &root, DEFAULT_MAX_BYTES).unwrap_err();
    assert!(err.contains("'$fixture' must be a string"), "{err}");
    let err = resolve_fixture(
        &json!({ "$fixture": "common/fixtures/html-parser/x", "compression": "zstd" }),
        &root,
        DEFAULT_MAX_BYTES,
    )
    .unwrap_err();
    assert!(err.contains("unsupported compression"), "{err}");
    let err = resolve_fixture(
        &json!({ "$fixture": "common/fixtures/html-parser/x", "encoding": "latin-1" }),
        &root,
        DEFAULT_MAX_BYTES,
    )
    .unwrap_err();
    assert!(err.contains("unsupported encoding"), "{err}");
}

// ---------------------------------------------------------------------------
// Parsing-core edge behavior (inline HTML fragments).
// ---------------------------------------------------------------------------

const BASE: &str = "https://www.newworld.co.nz/shop/search?pg=1&q=eggs";

fn page(body: &str) -> String {
    format!("<html><body><div id=\"search\">{body}</div></body></html>")
}

fn card(testid: &str, inner: &str) -> String {
    format!("<div itemtype=\"https://schema.org/Product\" data-testid=\"{testid}\">{inner}</div>")
}

const TITLE_AND_LINK: &str =
    "<p data-testid=\"product-title\">Eggs</p><a href=\"/shop/product/1?name=eggs\">x</a>";

fn parsed(body: &str) -> SearchResults {
    parse_search_results(&page(body), BASE).expect("expected ok result")
}

fn price_group(dollars: &str, cents: &str, per: &str) -> String {
    format!(
        "<div data-testid=\"price\"><p data-testid=\"price-dollars\">{dollars}</p>\
         <p data-testid=\"price-cents\">{cents}</p><p data-testid=\"price-per\">{per}</p></div>"
    )
}

#[test]
fn document_without_results_container_is_a_parse_error() {
    let result = parse_search_results("<html><body><p>nothing</p></body></html>", BASE);
    let error = result.expect_err("expected err result");
    assert_eq!(error.code, "no-results-container");
    assert_eq!(
        error.message,
        "no search results container (id=\"search\") in document"
    );
}

#[test]
fn container_with_zero_cards_is_ok_and_empty() {
    let results = parsed("<p>no products match</p>");
    assert_eq!(results.site, "new-world");
    assert_eq!(results.source_url, BASE);
    assert_eq!(results.next_page_url, None);
    assert_eq!(results.products, vec![]);
}

#[test]
fn full_card_extracts_every_field() {
    let body = card(
        "product-1-EA",
        &format!(
            "<a href=\"/shop/product/1?name=eggs&amp;tr=abc#frag\">\
             <p data-testid=\"product-title\"> Eggs <span>Dozen</span> </p>\
             <p data-testid=\"product-subtitle\">12pk</p></a>\
             <img data-testid=\"product-image\" src=\"https://img.test/1.png?w=384\">\
             {}<p data-testid=\"non-promo-unit-price\">$0.81/ea</p>",
            price_group("9", "73", "ea")
        ),
    );
    let results = parsed(&body);
    assert_eq!(results.products.len(), 1);
    let product = &results.products[0];
    assert_eq!(product.product_id, "1-EA");
    assert_eq!(product.name, "Eggs Dozen");
    assert_eq!(product.subtitle.as_deref(), Some("12pk"));
    assert_eq!(
        product.url,
        "https://www.newworld.co.nz/shop/product/1?name=eggs"
    );
    assert_eq!(
        product.image_url.as_deref(),
        Some("https://img.test/1.png?w=384")
    );
    let price = product.price.as_ref().expect("price");
    assert_eq!(
        (
            price.amount_cents,
            price.per.as_str(),
            price.display.as_str()
        ),
        (973, "ea", "$9.73")
    );
    let unit_price = product.unit_price.as_ref().expect("unit price");
    assert_eq!(
        (
            unit_price.amount_cents,
            unit_price.unit.as_str(),
            unit_price.display.as_str()
        ),
        (81, "ea", "$0.81/ea")
    );
}

#[test]
fn optional_fields_absent_become_none() {
    let results = parsed(&card("product-2", TITLE_AND_LINK));
    let product = &results.products[0];
    assert_eq!(product.subtitle, None);
    assert_eq!(product.image_url, None);
    assert_eq!(product.price, None);
    assert_eq!(product.unit_price, None);
}

#[test]
fn empty_subtitle_element_is_kept_as_empty_string() {
    let body = card(
        "product-2",
        &format!("{TITLE_AND_LINK}<p data-testid=\"product-subtitle\"> </p>"),
    );
    assert_eq!(parsed(&body).products[0].subtitle.as_deref(), Some(""));
}

#[test]
fn image_without_src_is_none() {
    let body = card(
        "product-2",
        &format!("{TITLE_AND_LINK}<img data-testid=\"product-image\">"),
    );
    assert_eq!(parsed(&body).products[0].image_url, None);
}

#[test]
fn relative_image_src_resolves_against_source_url() {
    let body = card(
        "product-2",
        &format!("{TITLE_AND_LINK}<img data-testid=\"product-image\" src=\"/img/1.png\">"),
    );
    assert_eq!(
        parsed(&body).products[0].image_url.as_deref(),
        Some("https://www.newworld.co.nz/img/1.png")
    );
}

#[test]
fn incomplete_price_groups_are_none() {
    for group in [
        // missing dollars / cents / per elements inside the group
        "<div data-testid=\"price\"><p data-testid=\"price-cents\">73</p><p data-testid=\"price-per\">ea</p></div>".to_string(),
        "<div data-testid=\"price\"><p data-testid=\"price-dollars\">9</p><p data-testid=\"price-per\">ea</p></div>".to_string(),
        "<div data-testid=\"price\"><p data-testid=\"price-dollars\">9</p><p data-testid=\"price-cents\">73</p></div>".to_string(),
        // malformed digit content
        price_group("nine", "73", "ea"),
        price_group("", "73", "ea"),
        price_group("9", "7", "ea"),
        price_group("9", "735", "ea"),
        price_group("9", "7x", "ea"),
        // u32 overflow: unparseable dollars, mul overflow, add overflow
        price_group("4294967296", "00", "ea"),
        price_group("42949673", "00", "ea"),
        price_group("42949672", "96", "ea"),
    ] {
        let results = parsed(&card("product-2", &format!("{TITLE_AND_LINK}{group}")));
        assert_eq!(results.products[0].price, None, "group: {group}");
    }
}

#[test]
fn price_amount_at_u32_maximum_is_kept() {
    let body = card(
        "product-2",
        &format!("{TITLE_AND_LINK}{}", price_group("42949672", "95", "ea")),
    );
    let results = parsed(&body);
    let price = results.products[0].price.as_ref().expect("price");
    assert_eq!(price.amount_cents, 4294967295);
    assert_eq!(price.display, "$42949672.95");
}

#[test]
fn malformed_unit_price_texts_are_none() {
    for text in [
        "0.81/ea",           // no $ prefix
        "$0.81",             // no unit separator
        "$81/ea",            // no decimal point
        "$x.81/ea",          // non-digit dollars
        "$0.8/ea",           // one-digit cents
        "$0.811/ea",         // three-digit cents
        "$0.8x/ea",          // non-digit cents
        "$0.81/",            // empty unit
        "$4294967296.00/ea", // dollars beyond u32
        "$42949673.00/ea",   // mul overflow
        "$42949672.96/ea",   // add overflow
    ] {
        let body = card(
            "product-2",
            &format!("{TITLE_AND_LINK}<p data-testid=\"non-promo-unit-price\">{text}</p>"),
        );
        assert_eq!(parsed(&body).products[0].unit_price, None, "text: {text}");
    }
}

#[test]
fn cards_missing_required_parts_are_skipped() {
    for (label, body) in [
        (
            "no data-testid",
            "<div itemtype=\"https://schema.org/Product\"><p data-testid=\"product-title\">Eggs</p><a href=\"/p/1\">x</a></div>".to_string(),
        ),
        ("testid without product- prefix", card("item-1", TITLE_AND_LINK)),
        ("no product-title", card("product-1", "<a href=\"/p/1\">x</a>")),
        (
            "no link with href",
            card("product-1", "<p data-testid=\"product-title\">Eggs</p><a>x</a>"),
        ),
    ] {
        let results = parsed(&body);
        assert_eq!(results.products, vec![], "case: {label}");
    }
}

#[test]
fn bare_product_prefix_yields_empty_product_id() {
    let results = parsed(&card("product-", TITLE_AND_LINK));
    assert_eq!(results.products[0].product_id, "");
}

#[test]
fn cards_are_deduplicated_by_canonical_url_in_document_order() {
    let body = format!(
        "{}{}{}",
        card(
            "product-1",
            "<p data-testid=\"product-title\">First</p><a href=\"/p/1?name=eggs&amp;tr=aaa\">x</a>"
        ),
        card(
            "product-2",
            "<p data-testid=\"product-title\">Duplicate</p><a href=\"/p/1?name=eggs&amp;tr=bbb\">x</a>"
        ),
        card(
            "product-3",
            "<p data-testid=\"product-title\">Distinct</p><a href=\"/p/2\">x</a>"
        ),
    );
    let results = parsed(&body);
    let summary: Vec<(&str, &str)> = results
        .products
        .iter()
        .map(|product| (product.name.as_str(), product.url.as_str()))
        .collect();
    assert_eq!(
        summary,
        vec![
            ("First", "https://www.newworld.co.nz/p/1?name=eggs"),
            ("Distinct", "https://www.newworld.co.nz/p/2"),
        ]
    );
}

#[test]
fn cards_outside_the_container_are_still_extracted() {
    let html = format!(
        "<html><body><div id=\"search\"></div>{}</body></html>",
        card("product-9", TITLE_AND_LINK)
    );
    let results = parse_search_results(&html, BASE).expect("ok");
    assert_eq!(results.products.len(), 1);
}

#[test]
fn next_page_link_is_resolved_and_first_match_wins() {
    let results = parsed(
        "<a href=\"/elsewhere\">plain</a>\
         <a rel=\"prev\" href=\"?pg=0\">prev</a>\
         <a rel=\"prefetch NEXT\" href=\"?pg=2\">next</a>\
         <a rel=\"next\" href=\"?pg=3\">later next</a>",
    );
    assert_eq!(
        results.next_page_url.as_deref(),
        Some("https://www.newworld.co.nz/shop/search?pg=2")
    );
}

#[test]
fn next_rel_without_href_is_skipped() {
    let results = parsed("<a rel=\"next\">no href</a>");
    assert_eq!(results.next_page_url, None);
}

#[test]
fn resolve_url_handles_every_reference_form() {
    let base = "https://host.test/a/b?q=1";
    for (href, expected) in [
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
        // not absolute URLs: scheme must start alphabetic and use valid chars
        ("1abc:x", "https://host.test/a/1abc:x"),
        (":x", "https://host.test/a/:x"),
        ("ht~tp:x", "https://host.test/a/ht~tp:x"),
    ] {
        assert_eq!(resolve_url(base, href), expected, "href: {href}");
    }
}

#[test]
fn resolve_url_handles_degenerate_bases() {
    // Base without a fragment-free query, without an authority, without a
    // path, and without a scheme -- each keeps resolution deterministic.
    assert_eq!(
        resolve_url("https://host.test/a/b?q=1#frag", "#f2"),
        "https://host.test/a/b?q=1#f2"
    );
    assert_eq!(
        resolve_url("https://host.test/a/b", "#f"),
        "https://host.test/a/b#f"
    );
    assert_eq!(
        resolve_url("https://host.test", "rel"),
        "https://host.test/rel"
    );
    assert_eq!(
        resolve_url("mailto:someone@host.test", "rel"),
        "mailto:/rel"
    );
    assert_eq!(resolve_url("no-scheme/path", "rel"), "/no-scheme/rel");
}

#[test]
fn remove_dot_segments_normalizes_paths() {
    for (path, expected) in [
        ("/a/b/../c", "/a/c"),
        ("/a/./b", "/a/b"),
        ("/..", "/"),
        ("/a/b/..", "/a/"),
        ("/a/.", "/a/"),
        ("/a/b", "/a/b"),
    ] {
        assert_eq!(remove_dot_segments(path), expected, "path: {path}");
    }
}

#[test]
fn canonical_card_url_strips_tr_and_fragment_only() {
    let base = "https://host.test/shop/search?pg=1";
    for (href, expected) in [
        ("/p/1?name=eggs&tr=zzz", "https://host.test/p/1?name=eggs"),
        ("/p/1?tr=zzz&name=eggs", "https://host.test/p/1?name=eggs"),
        ("/p/1?a=1&tr=zzz&b=2", "https://host.test/p/1?a=1&b=2"),
        ("/p/1?tr=zzz", "https://host.test/p/1"),
        ("/p/1?tr", "https://host.test/p/1"),
        ("/p/1?trx=1&x=tr", "https://host.test/p/1?trx=1&x=tr"),
        ("/p/1?a=1&&b=2", "https://host.test/p/1?a=1&&b=2"),
        ("/p/1#frag", "https://host.test/p/1"),
        ("/p/1", "https://host.test/p/1"),
    ] {
        assert_eq!(canonical_card_url(base, href), expected, "href: {href}");
    }
}
