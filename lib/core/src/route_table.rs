//! Fast in-memory route resolution table.
//!
//! Holds an ordered list of [`PathMatcher`] entries (with optional method/scope filters) and
//! resolves an incoming ``(path, scope_type, method)`` tuple in a single pass, returning a
//! typed [`Resolution`] alongside the matched route's metadata.

use pyo3::prelude::*;
use pyo3::types::PyTuple;

use crate::url::{MatchKind, PathMatcher};

#[derive(Clone)]
struct RouteEntry {
    matcher: PathMatcher,
    scope_type_mask: u8,
    accept_partial_path: bool,
    methods: Option<Vec<String>>,
}

/// Outcome of [`RouteTable::resolve`].
#[pyclass(eq, eq_int, frozen, skip_from_py_object)]
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Resolution {
    /// Exact match (returned tuple shape: ``(0, index, params, matched, unmatched)``).
    Full = 0,
    /// Partial match against a mounted route (returned tuple shape: ``(1, index, params,
    /// matched, unmatched)``).
    Mount = 1,
    /// A path matched but the request method is not allowed (returned tuple shape:
    /// ``(2, first_partial_index, allowed_methods)``).
    MethodNotAllowed = 2,
}

/// Pure-Rust outcome of route resolution prior to converting to Python objects.
enum ResolveOutcome<'a> {
    Match {
        kind: Resolution,
        index: usize,
        param_vals: Vec<&'a str>,
        matched: &'a str,
        unmatched: &'a str,
    },
    MethodNotAllowed {
        index: usize,
        allowed_methods: Vec<String>,
    },
    NotFound,
}

#[pyclass]
struct RouteTable {
    entries: Vec<RouteEntry>,
}

impl RouteTable {
    /// Pure-Rust route resolution shared by the Python binding and the unit tests.
    fn resolve_inner<'a>(&self, path: &'a str, scope_type: u8, method: &str) -> ResolveOutcome<'a> {
        let mut partial_index: Option<usize> = None;
        let mut allowed_methods: Vec<String> = Vec::new();

        for (index, entry) in self.entries.iter().enumerate() {
            if entry.scope_type_mask & scope_type == 0 {
                continue;
            }

            let Some((match_kind, param_vals, matched, unmatched)) = entry.matcher.match_path_raw(path) else {
                continue;
            };

            if match_kind == MatchKind::Partial && !entry.accept_partial_path {
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

            let kind = if entry.accept_partial_path {
                Resolution::Mount
            } else {
                Resolution::Full
            };
            return ResolveOutcome::Match {
                kind,
                index,
                param_vals,
                matched,
                unmatched,
            };
        }

        partial_index.map_or(ResolveOutcome::NotFound, |index| ResolveOutcome::MethodNotAllowed {
            index,
            allowed_methods,
        })
    }
}

#[pymethods]
impl RouteTable {
    #[new]
    const fn new() -> Self {
        Self { entries: Vec::new() }
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

    /// Resolve a route for the given ``(path, scope_type, method)`` tuple.
    ///
    /// Returns ``None`` for not-found, otherwise a tuple where the first element is a
    /// [`Resolution`] variant comparable to its integer value:
    ///
    /// - [`Resolution::Full`] — ``(0, index, params, matched, unmatched)``
    /// - [`Resolution::Mount`] — ``(1, index, params, matched, unmatched)``
    /// - [`Resolution::MethodNotAllowed`] — ``(2, index, allowed_methods)``
    #[allow(clippy::cast_possible_wrap)]
    fn resolve<'py>(&self, py: Python<'py>, path: &'py str, scope_type: u8, method: &str) -> PyResult<Py<PyAny>> {
        match self.resolve_inner(path, scope_type, method) {
            ResolveOutcome::Match {
                kind,
                index,
                param_vals,
                matched,
                unmatched,
            } => {
                let vals_tuple = PyTuple::new(py, &param_vals)?;
                let matched_opt: Option<&str> = if matched.is_empty() { None } else { Some(matched) };
                let unmatched_opt: Option<&str> = if unmatched.is_empty() { None } else { Some(unmatched) };

                let result = (kind, index as i64, vals_tuple, matched_opt, unmatched_opt);
                Ok(result.into_pyobject(py)?.into_any().unbind())
            }
            ResolveOutcome::MethodNotAllowed { index, allowed_methods } => {
                let methods_tuple = PyTuple::new(py, &allowed_methods)?;
                let result = (Resolution::MethodNotAllowed, index as i64, methods_tuple);
                Ok(result.into_pyobject(py)?.into_any().unbind())
            }
            ResolveOutcome::NotFound => Ok(py.None()),
        }
    }
}

pub fn build(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RouteTable>()?;
    m.add_class::<Resolution>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn matcher(template: &[(bool, &str, &str)]) -> PathMatcher {
        let segments: Vec<(bool, String, String)> = template
            .iter()
            .map(|(p, v, t)| (*p, (*v).to_owned(), (*t).to_owned()))
            .collect();
        PathMatcher::new(true, false, segments)
    }

    fn table_with_entries(entries: Vec<(PathMatcher, u8, bool, Option<Vec<String>>)>) -> RouteTable {
        let mut t = RouteTable::new();
        for (m, mask, partial, methods) in entries {
            t.add_entry(&m, mask, partial, methods);
        }
        t
    }

    #[test]
    fn resolve_full_match() {
        let t = table_with_entries(vec![(
            matcher(&[(false, "users", ""), (true, "id", "int")]),
            0xFF,
            false,
            Some(vec!["GET".to_string()]),
        )]);

        match t.resolve_inner("/users/1", 0xFF, "GET") {
            ResolveOutcome::Match {
                kind,
                index,
                param_vals,
                ..
            } => {
                assert_eq!(kind, Resolution::Full);
                assert_eq!(index, 0);
                assert_eq!(param_vals, vec!["1"]);
            }
            other => panic!("expected full match, got {:?}", outcome_label(&other)),
        }
    }

    #[test]
    fn resolve_mount_match_for_partial_route() {
        let t = table_with_entries(vec![(matcher(&[(false, "api", "")]), 0xFF, true, None)]);

        match t.resolve_inner("/api/v1/health", 0xFF, "GET") {
            ResolveOutcome::Match {
                kind,
                matched,
                unmatched,
                ..
            } => {
                assert_eq!(kind, Resolution::Mount);
                assert_eq!(matched, "/api");
                assert_eq!(unmatched, "/v1/health");
            }
            other => panic!("expected mount match, got {:?}", outcome_label(&other)),
        }
    }

    #[test]
    fn resolve_method_not_allowed() {
        let t = table_with_entries(vec![(
            matcher(&[(false, "users", "")]),
            0xFF,
            false,
            Some(vec!["GET".to_string()]),
        )]);

        match t.resolve_inner("/users", 0xFF, "POST") {
            ResolveOutcome::MethodNotAllowed { index, allowed_methods } => {
                assert_eq!(index, 0);
                assert_eq!(allowed_methods, vec!["GET".to_string()]);
            }
            other => panic!("expected method not allowed, got {:?}", outcome_label(&other)),
        }
    }

    #[test]
    fn resolve_not_found_when_no_entry_matches() {
        let t = table_with_entries(vec![(matcher(&[(false, "users", "")]), 0xFF, false, None)]);

        assert!(matches!(
            t.resolve_inner("/posts", 0xFF, "GET"),
            ResolveOutcome::NotFound
        ));
    }

    #[test]
    fn resolve_skips_entries_with_disjoint_scope_mask() {
        let t = table_with_entries(vec![(matcher(&[(false, "users", "")]), 0b0001, false, None)]);

        assert!(matches!(
            t.resolve_inner("/users", 0b0010, "GET"),
            ResolveOutcome::NotFound
        ));
    }

    fn outcome_label(o: &ResolveOutcome<'_>) -> &'static str {
        match o {
            ResolveOutcome::Match { .. } => "Match",
            ResolveOutcome::MethodNotAllowed { .. } => "MethodNotAllowed",
            ResolveOutcome::NotFound => "NotFound",
        }
    }
}
