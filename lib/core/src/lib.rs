//! Native (Rust) extension powering hot paths of [Flama](https://flama.dev).
//!
//! The crate exposes a single Python module, `flama._core`, that aggregates a number of
//! topic-scoped submodules — each implementing a thin `PyO3` binding around a pure-Rust
//! implementation. Submodules are registered through [`register_submodule`], which keeps the
//! per-module boilerplate (creating the `PyModule`, adding it to the parent, and publishing it
//! under `sys.modules`) in one place.
//!
//! The Python-visible surface lives in `flama/_core/*.pyi` stubs.

use pyo3::prelude::*;

mod compression;
mod cookies;
mod http;
mod json_encoder;
mod multipart;
mod route_table;
mod url;

/// Register a new submodule under `parent` and publish it as `flama._core.<name>` in
/// `sys.modules`, so that `import flama._core.<name>` succeeds.
///
/// `build` populates the new module with its classes/functions.
fn register_submodule(
    parent: &Bound<'_, PyModule>,
    name: &str,
    build: impl FnOnce(&Bound<'_, PyModule>) -> PyResult<()>,
) -> PyResult<()> {
    let m = PyModule::new(parent.py(), name)?;
    build(&m)?;
    parent.add_submodule(&m)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item(format!("flama._core.{name}"), &m)?;
    Ok(())
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    register_submodule(m, "compression", compression::build)?;
    register_submodule(m, "cookies", cookies::build)?;
    register_submodule(m, "http", http::build)?;
    register_submodule(m, "json_encoder", json_encoder::build)?;
    register_submodule(m, "multipart", multipart::build)?;
    register_submodule(m, "route_table", route_table::build)?;
    register_submodule(m, "url", url::build)?;
    Ok(())
}
