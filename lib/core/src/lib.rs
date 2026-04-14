use pyo3::prelude::*;

mod compression;
mod json_encoder;
mod multipart;
mod route_table;
mod url;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    compression::register(m)?;
    json_encoder::register(m)?;
    multipart::register(m)?;
    route_table::register(m)?;
    url::register(m)?;
    Ok(())
}
