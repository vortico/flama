use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

/// Parse a ``Content-Type`` header into ``(media_type, params)``.
///
/// The media type is lowercased.  Parameters are split on ``;``, keys are
/// lowercased, and surrounding double-quotes on values are stripped.
#[pyfunction]
fn parse_content_type<'py>(
    py: Python<'py>,
    header: &str,
) -> PyResult<(String, Bound<'py, PyDict>)> {
    let mut parts = header.splitn(2, ';');
    let media_type = parts
        .next()
        .unwrap_or("")
        .trim()
        .to_ascii_lowercase();

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

    let dict = PyDict::new(py);
    for (k, v) in &params {
        dict.set_item(k, v)?;
    }
    Ok((media_type, dict))
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "http")?;
    m.add_function(wrap_pyfunction!(parse_content_type, &m)?)?;
    parent.add_submodule(&m)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item("flama._core.http", &m)?;
    Ok(())
}
