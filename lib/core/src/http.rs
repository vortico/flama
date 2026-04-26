//! HTTP header parsing primitives.
//!
//! Currently exposes a single helper, [`parse_content_type`], that splits a
//! ``Content-Type`` header value into a media-type and a parameter dictionary.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

/// Parse a ``Content-Type`` header into ``(media_type, params)``.
///
/// The media type is lowercased.  Parameters are split on ``;``, keys are
/// lowercased, and surrounding double-quotes on values are stripped.
#[pyfunction]
fn parse_content_type<'py>(py: Python<'py>, header: &str) -> PyResult<(String, Bound<'py, PyDict>)> {
    let (media_type, params) = parse_content_type_inner(header);

    let dict = PyDict::new(py);
    for (k, v) in &params {
        dict.set_item(k, v)?;
    }
    Ok((media_type, dict))
}

/// Pure-Rust ``Content-Type`` parser shared by the Python binding and the unit tests.
///
/// The media type is lowercased; parameter keys are lowercased; surrounding
/// double-quotes on values are stripped.
fn parse_content_type_inner(header: &str) -> (String, HashMap<String, String>) {
    let mut parts = header.splitn(2, ';');
    let media_type = parts.next().unwrap_or("").trim().to_ascii_lowercase();

    let mut params = HashMap::new();
    if let Some(rest) = parts.next() {
        for param in rest.split(';') {
            let param = param.trim();
            if let Some((k, v)) = param.split_once('=') {
                let key = k.trim().to_ascii_lowercase();
                let val = v.trim().trim_matches('"').to_owned();
                params.insert(key, val);
            }
        }
    }
    (media_type, params)
}

pub fn build(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_content_type, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lowercases_media_type() {
        let (mt, _) = parse_content_type_inner("APPLICATION/JSON");
        assert_eq!(mt, "application/json");
    }

    #[test]
    fn parses_charset_and_boundary() {
        let (mt, params) = parse_content_type_inner("multipart/form-data; charset=UTF-8; boundary=----xyz");
        assert_eq!(mt, "multipart/form-data");
        assert_eq!(params.get("charset"), Some(&"UTF-8".to_owned()));
        assert_eq!(params.get("boundary"), Some(&"----xyz".to_owned()));
    }

    #[test]
    fn lowercases_param_keys_and_strips_value_quotes() {
        let (_mt, params) = parse_content_type_inner("text/plain; CharSet=\"utf-8\"");
        assert_eq!(params.get("charset"), Some(&"utf-8".to_owned()));
    }

    #[test]
    fn handles_missing_params() {
        let (mt, params) = parse_content_type_inner("text/html");
        assert_eq!(mt, "text/html");
        assert!(params.is_empty());
    }

    #[test]
    fn handles_empty_header() {
        let (mt, params) = parse_content_type_inner("");
        assert_eq!(mt, "");
        assert!(params.is_empty());
    }

    #[test]
    fn skips_param_without_equals() {
        let (mt, params) = parse_content_type_inner("text/plain; orphan; charset=ascii");
        assert_eq!(mt, "text/plain");
        assert_eq!(params.len(), 1);
        assert_eq!(params.get("charset"), Some(&"ascii".to_owned()));
    }
}
