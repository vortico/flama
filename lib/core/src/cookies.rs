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
    cookie::Cookie::split_parse(header)
        .filter_map(|r| r.ok())
        .map(|c| (c.name().to_owned(), c.value().to_owned()))
        .collect()
}

/// Build a ``Set-Cookie`` header value (RFC 6265) from the given parameters.
///
/// Returns the full header value string ready to be appended as a
/// ``set-cookie`` response header.
#[pyfunction]
#[pyo3(signature = (key, value="", max_age=None, expires=None, path=None, domain=None, secure=false, httponly=false, samesite=None, partitioned=false))]
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
            _ => {
                return Err(PyValueError::new_err(
                    "samesite must be 'strict', 'lax', or 'none'",
                ))
            }
        };
        c.set_same_site(ss);
    }

    if partitioned {
        c.set_partitioned(true);
    }

    Ok(c.to_string())
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "cookies")?;
    m.add_function(wrap_pyfunction!(parse_cookie_header, &m)?)?;
    m.add_function(wrap_pyfunction!(build_cookie_header, &m)?)?;
    parent.add_submodule(&m)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item("flama._core.cookies", &m)?;
    Ok(())
}
