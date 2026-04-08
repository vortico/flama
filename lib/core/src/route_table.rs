use pyo3::prelude::*;
use pyo3::types::PyTuple;

use crate::url::PathMatcher;

#[derive(Clone)]
struct RouteEntry {
    matcher: PathMatcher,
    scope_type_mask: u8,
    accept_partial_path: bool,
    methods: Option<Vec<String>>,
}

/// Result variants returned to Python:
///
/// Full match:        (0, index, param_values, matched, unmatched)
/// Mount match:       (1, index, param_values, matched, unmatched)
/// MethodNotAllowed:  (2, first_partial_index, allowed_methods)
/// NotFound:          None
#[pyclass]
struct RouteTable {
    entries: Vec<RouteEntry>,
}

#[pymethods]
impl RouteTable {
    #[new]
    fn new() -> Self {
        RouteTable {
            entries: Vec::new(),
        }
    }

    #[pyo3(signature = (matcher, scope_type_mask, accept_partial_path, methods=None))]
    fn add_entry(
        &mut self,
        matcher: &PathMatcher,
        scope_type_mask: u8,
        accept_partial_path: bool,
        methods: Option<Vec<String>>,
    ) {
        self.entries.push(RouteEntry {
            matcher: matcher.clone(),
            scope_type_mask,
            accept_partial_path,
            methods,
        });
    }

    fn resolve<'py>(
        &self,
        py: Python<'py>,
        path: &'py str,
        scope_type: u8,
        method: &str,
    ) -> PyResult<Py<PyAny>> {
        let mut partial_index: Option<usize> = None;
        let mut allowed_methods: Vec<String> = Vec::new();

        for (index, entry) in self.entries.iter().enumerate() {
            if entry.scope_type_mask & scope_type == 0 {
                continue;
            }

            let result = entry.matcher.match_path_raw(path);
            let (match_type, param_vals, matched, unmatched) = match result {
                Some(r) => r,
                None => continue,
            };

            // match_type: 1=exact, 2=partial
            if match_type == 2 && !entry.accept_partial_path {
                continue;
            }

            if let Some(ref methods) = entry.methods {
                if !methods.iter().any(|m| m == method) {
                    if partial_index.is_none() {
                        partial_index = Some(index);
                    }
                    allowed_methods.extend(methods.iter().cloned());
                    continue;
                }
            }

            let result_type: i32 = if entry.accept_partial_path { 1 } else { 0 };
            let vals_tuple = PyTuple::new(py, &param_vals)?;
            let matched_opt: Option<&str> = if matched.is_empty() {
                None
            } else {
                Some(matched)
            };
            let unmatched_opt: Option<&str> = if unmatched.is_empty() {
                None
            } else {
                Some(unmatched)
            };

            let result = (
                result_type,
                index as i64,
                vals_tuple,
                matched_opt,
                unmatched_opt,
            );
            return Ok(result.into_pyobject(py)?.into_any().unbind());
        }

        if let Some(idx) = partial_index {
            let methods_tuple = PyTuple::new(py, &allowed_methods)?;
            let result = (2i32, idx as i64, methods_tuple);
            return Ok(result.into_pyobject(py)?.into_any().unbind());
        }

        Ok(py.None())
    }
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "route_table")?;
    m.add_class::<RouteTable>()?;
    parent.add_submodule(&m)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item("flama._core.route_table", &m)?;
    Ok(())
}
