//! HTTP cookie parsing and serialisation primitives.
//!
//! Thin Python bindings over the [`cookie`] crate that mirror the request-side
//! ``Cookie`` header parser and the response-side ``Set-Cookie`` builder.

use cookie::time::{Duration, OffsetDateTime};
use cookie::SameSite;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// Parse a ``Cookie`` request header (RFC 6265) into a list of ``(name, value)`` tuples.
///
/// Uses the `cookie` crate's `Cookie::split_parse` which correctly handles
/// quoted values, whitespace, and edge cases per the RFC.  Malformed pairs
/// are silently skipped, matching stdlib ``SimpleCookie`` behaviour.
#[pyfunction]
fn parse_cookie_header(header: &str) -> Vec<(String, String)> {
    parse_cookie_header_inner(header)
}

/// Pure-Rust cookie header parser used by both the Python binding and the unit tests.
fn parse_cookie_header_inner(header: &str) -> Vec<(String, String)> {
    cookie::Cookie::split_parse(header)
        .filter_map(Result::ok)
        .map(|c| (c.name().to_owned(), c.value().to_owned()))
        .collect()
}

/// Build a ``Set-Cookie`` header value (RFC 6265) from the given parameters.
///
/// Returns the full header value string ready to be appended as a
/// ``set-cookie`` response header.
#[pyfunction]
#[pyo3(signature = (key, value="", max_age=None, expires=None, path=None, domain=None, secure=false, httponly=false, samesite=None, partitioned=false))]
#[allow(clippy::too_many_arguments)]
fn build_cookie_header(
    key: &str,
    value: &str,
    max_age: Option<i64>,
    expires: Option<i64>,
    path: Option<&str>,
    domain: Option<&str>,
    secure: bool,
    httponly: bool,
    samesite: Option<&str>,
    partitioned: bool,
) -> PyResult<String> {
    build_cookie_header_inner(
        key,
        value,
        max_age,
        expires,
        path,
        domain,
        secure,
        httponly,
        samesite,
        partitioned,
    )
}

#[allow(clippy::too_many_arguments, clippy::fn_params_excessive_bools)]
fn build_cookie_header_inner(
    key: &str,
    value: &str,
    max_age: Option<i64>,
    expires: Option<i64>,
    path: Option<&str>,
    domain: Option<&str>,
    secure: bool,
    httponly: bool,
    samesite: Option<&str>,
    partitioned: bool,
) -> PyResult<String> {
    let mut c = cookie::Cookie::new(key, value);

    if let Some(secs) = max_age {
        c.set_max_age(Duration::seconds(secs));
    }

    if let Some(ts) = expires {
        let dt = OffsetDateTime::from_unix_timestamp(ts)
            .map_err(|e| PyValueError::new_err(format!("invalid expires timestamp: {e}")))?;
        c.set_expires(dt);
    }

    if let Some(p) = path {
        c.set_path(p);
    }

    if let Some(d) = domain {
        c.set_domain(d);
    }

    c.set_secure(secure);
    c.set_http_only(httponly);

    if let Some(ss) = samesite {
        let ss = match ss.to_lowercase().as_str() {
            "strict" => SameSite::Strict,
            "lax" => SameSite::Lax,
            "none" => SameSite::None,
            _ => return Err(PyValueError::new_err("samesite must be 'strict', 'lax', or 'none'")),
        };
        c.set_same_site(ss);
    }

    if partitioned {
        c.set_partitioned(true);
    }

    Ok(c.to_string())
}

pub fn build(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_cookie_header, m)?)?;
    m.add_function(wrap_pyfunction!(build_cookie_header, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_simple_pair() {
        let pairs = parse_cookie_header_inner("a=1; b=2");
        assert_eq!(
            pairs,
            vec![("a".to_owned(), "1".to_owned()), ("b".to_owned(), "2".to_owned())]
        );
    }

    #[test]
    fn parse_keeps_quoted_value_and_handles_whitespace() {
        let pairs = parse_cookie_header_inner("name=\"hello world\";  empty=");
        assert_eq!(
            pairs,
            vec![
                ("name".to_owned(), "\"hello world\"".to_owned()),
                ("empty".to_owned(), String::new()),
            ]
        );
    }

    #[test]
    fn parse_skips_malformed() {
        let pairs = parse_cookie_header_inner("nope; ok=yes");
        assert_eq!(pairs, vec![("ok".to_owned(), "yes".to_owned())]);
    }

    fn build(samesite: Option<&str>, expires: Option<i64>) -> PyResult<String> {
        build_cookie_header_inner(
            "session",
            "abc",
            None,
            expires,
            Some("/"),
            None,
            true,
            true,
            samesite,
            false,
        )
    }

    #[test]
    fn build_emits_secure_and_httponly() {
        let h = build(None, None).expect("build_cookie_header");
        assert!(h.starts_with("session=abc;"));
        assert!(h.contains("Secure"));
        assert!(h.contains("HttpOnly"));
        assert!(h.contains("Path=/"));
    }

    #[test]
    fn build_parses_samesite() {
        let h = build(Some("Lax"), None).expect("build_cookie_header");
        assert!(h.contains("SameSite=Lax"));

        let h = build(Some("strict"), None).expect("build_cookie_header");
        assert!(h.contains("SameSite=Strict"));

        build(Some("invalid"), None).expect_err("invalid samesite must error");
    }

    #[test]
    fn build_rejects_invalid_expires() {
        build(None, Some(i64::MAX)).expect_err("out-of-range timestamp must error");
    }
}
