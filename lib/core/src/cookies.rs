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

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "cookies")?;
    m.add_function(wrap_pyfunction!(parse_cookie_header, &m)?)?;
    parent.add_submodule(&m)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item("flama._core.cookies", &m)?;
    Ok(())
}
