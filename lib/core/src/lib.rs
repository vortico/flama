use pyo3::prelude::*;

mod json_encoder;
mod url;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    json_encoder::register(m)?;
    url::register(m)?;
    Ok(())
}
