use pyo3::prelude::*;

mod json_encoder;
mod multipart;
mod route_table;
mod url;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    json_encoder::register(m)?;
    multipart::register(m)?;
    route_table::register(m)?;
    url::register(m)?;
    Ok(())
}
