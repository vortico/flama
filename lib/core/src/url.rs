//! Path and netloc matching primitives.
//!
//! [`PathMatcher`] performs fast segment-based matching against a parsed path template,
//! returning a typed [`MatchKind`] (``Exact``/``Partial``) plus the captured raw parameter
//! slices. Type conversion is intentionally left to Python to avoid costly per-call object
//! creation across the FFI boundary.
//!
//! [`NetlocMatcher`] performs case-insensitive host matching with three pattern shapes:
//! ``*`` (any), ``*.example.com`` (wildcard subdomain), or an exact host.

use pyo3::prelude::*;
use pyo3::types::PyTuple;
use std::str::FromStr;

type MatchResult<'py> = Option<(MatchKind, Bound<'py, PyTuple>, Option<&'py str>, Option<&'py str>)>;

/// Outcome of [`PathMatcher::match_path_raw`].
#[pyclass(eq, eq_int, frozen, skip_from_py_object)]
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum MatchKind {
    /// The whole input was consumed by the template.
    Exact = 1,
    /// A prefix of the input was consumed; the remainder is in the ``unmatched`` field.
    Partial = 2,
}

/// One element of a parsed path template.
#[derive(Clone)]
enum Segment {
    Constant(String),
    Parameter { type_tag: TypeTag },
}

/// Validation tag for a parameter segment.
#[derive(Clone, Copy)]
enum TypeTag {
    Str,
    Int,
    Float,
    Decimal,
    Uuid,
}

impl FromStr for TypeTag {
    type Err = ();

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "str" => Ok(Self::Str),
            "int" => Ok(Self::Int),
            "float" => Ok(Self::Float),
            "decimal" => Ok(Self::Decimal),
            "uuid" => Ok(Self::Uuid),
            _ => Err(()),
        }
    }
}

/// Pre-parsed path template for fast segment-based matching.
#[pyclass(skip_from_py_object)]
#[derive(Clone)]
pub struct PathMatcher {
    has_starting_slash: bool,
    has_trailing_slash: bool,
    segments: Vec<Segment>,
    param_count: usize,
}

impl PathMatcher {
    /// Pure-Rust path matching without Python object creation.
    ///
    /// Returns ``(kind, param_values, matched, unmatched)`` or ``None`` on no-match.
    pub fn match_path_raw<'a>(&self, input: &'a str) -> Option<(MatchKind, Vec<&'a str>, &'a str, &'a str)> {
        let ib = input.as_bytes();
        let ilen = ib.len();
        let mut cursor: usize = 0;

        if self.has_starting_slash {
            if cursor >= ilen || ib[cursor] != b'/' {
                return None;
            }
            cursor += 1;
        }

        let mut param_vals: Vec<&str> = Vec::with_capacity(self.param_count);

        for (i, segment) in self.segments.iter().enumerate() {
            if i > 0 {
                if cursor >= ilen || ib[cursor] != b'/' {
                    return None;
                }
                cursor += 1;
            }

            match segment {
                Segment::Constant(value) => {
                    if value.is_empty() {
                        continue;
                    }
                    let vb = value.as_bytes();
                    let vlen = vb.len();
                    if cursor + vlen > ilen || &ib[cursor..cursor + vlen] != vb {
                        return None;
                    }
                    cursor += vlen;
                }
                Segment::Parameter { type_tag } => {
                    let remaining = &ib[cursor..];
                    let seg_len = remaining.iter().position(|&b| b == b'/').unwrap_or(remaining.len());
                    let seg = &remaining[..seg_len];
                    if !Self::validate(seg, *type_tag) {
                        return None;
                    }
                    param_vals.push(&input[cursor..cursor + seg_len]);
                    cursor += seg_len;
                }
            }
        }

        if self.has_trailing_slash {
            if cursor >= ilen || ib[cursor] != b'/' {
                return None;
            }
            cursor += 1;
        }

        let matched = &input[..cursor];
        let unmatched = &input[cursor..];
        let kind = if unmatched.is_empty() {
            MatchKind::Exact
        } else {
            MatchKind::Partial
        };

        Some((kind, param_vals, matched, unmatched))
    }

    #[inline]
    fn is_valid_int(s: &[u8]) -> bool {
        let s = if !s.is_empty() && s[0] == b'-' { &s[1..] } else { s };
        !s.is_empty() && s.iter().all(u8::is_ascii_digit)
    }

    #[inline]
    fn is_valid_float(s: &[u8]) -> bool {
        let s = if !s.is_empty() && s[0] == b'-' { &s[1..] } else { s };
        if s.is_empty() || !s[0].is_ascii_digit() {
            return false;
        }
        let digit_end = s.iter().position(|b| !b.is_ascii_digit()).unwrap_or(s.len());
        if digit_end == s.len() {
            return true;
        }
        if s[digit_end] != b'.' {
            return false;
        }
        let rest = &s[digit_end + 1..];
        !rest.is_empty() && rest.iter().all(u8::is_ascii_digit)
    }

    #[inline]
    fn is_valid_uuid(s: &[u8]) -> bool {
        s.len() == 36
            && s[8] == b'-'
            && s[13] == b'-'
            && s[18] == b'-'
            && s[23] == b'-'
            && s.iter().enumerate().all(|(i, &c)| {
                i == 8 || i == 13 || i == 18 || i == 23 || c.is_ascii_digit() || (b'a'..=b'f').contains(&c)
            })
    }

    #[inline]
    fn validate(seg: &[u8], tag: TypeTag) -> bool {
        match tag {
            TypeTag::Str => !seg.is_empty(),
            TypeTag::Int => Self::is_valid_int(seg),
            TypeTag::Float | TypeTag::Decimal => Self::is_valid_float(seg),
            TypeTag::Uuid => Self::is_valid_uuid(seg),
        }
    }
}

/// Stores a pre-parsed path template for fast segment-based matching.
///
/// Returns match results as ``(kind, param_values, matched, unmatched)`` where
/// `param_values` contains raw string slices — type conversion is done in Python
/// to avoid costly per-call object creation across the FFI boundary.
#[pymethods]
impl PathMatcher {
    #[new]
    #[pyo3(signature = (has_starting_slash, has_trailing_slash, segments))]
    pub fn new(has_starting_slash: bool, has_trailing_slash: bool, segments: Vec<(bool, String, String)>) -> Self {
        let mut param_count = 0;
        let parsed = segments
            .into_iter()
            .map(|(is_param, value, type_tag)| {
                if is_param {
                    param_count += 1;
                    Segment::Parameter {
                        type_tag: TypeTag::from_str(&type_tag).unwrap_or(TypeTag::Str),
                    }
                } else {
                    Segment::Constant(value)
                }
            })
            .collect();

        Self {
            has_starting_slash,
            has_trailing_slash,
            segments: parsed,
            param_count,
        }
    }

    /// Returns ``None`` on no-match, or a tuple ``(kind, param_values, matched, unmatched)``.
    ///
    /// `kind` is a [`MatchKind`] variant comparable to its integer value
    /// (``MatchKind.Exact == 1`` / ``MatchKind.Partial == 2``).
    /// `param_values` are raw strings in parameter declaration order; Python converts them
    /// to typed values.
    fn match_path<'py>(&self, py: Python<'py>, input: &'py str) -> PyResult<MatchResult<'py>> {
        let Some((kind, param_vals, matched, unmatched)) = self.match_path_raw(input) else {
            return Ok(None);
        };

        let vals_tuple = PyTuple::new(py, param_vals)?;
        let matched_opt = if matched.is_empty() { None } else { Some(matched) };
        let unmatched_opt = if unmatched.is_empty() { None } else { Some(unmatched) };

        Ok(Some((kind, vals_tuple, matched_opt, unmatched_opt)))
    }
}

/// Pre-parsed netloc pattern for fast host matching.
///
/// Supports three pattern forms:
///   - `"*"` — matches any host.
///   - `"*.example.com"` — matches any subdomain of `example.com`.
///   - `"example.com"` — exact match only.
#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct NetlocMatcher {
    kind: NetlocPatternKind,
}

#[derive(Clone, Debug)]
enum NetlocPatternKind {
    Any,
    WildcardSuffix(String),
    Exact(String),
}

#[pymethods]
impl NetlocMatcher {
    #[new]
    fn new(pattern: &str) -> PyResult<Self> {
        let kind = if pattern == "*" {
            NetlocPatternKind::Any
        } else if let Some(suffix) = pattern.strip_prefix("*.") {
            NetlocPatternKind::WildcardSuffix(format!(".{}", suffix.to_ascii_lowercase()))
        } else if pattern.contains('*') {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Domain wildcard patterns must be like '*.example.com'.",
            ));
        } else {
            NetlocPatternKind::Exact(pattern.to_ascii_lowercase())
        };
        Ok(Self { kind })
    }

    /// Check whether *host* matches this pattern.
    fn is_match(&self, host: &str) -> bool {
        let host_lower = host.to_ascii_lowercase();
        match &self.kind {
            NetlocPatternKind::Any => true,
            NetlocPatternKind::Exact(expected) => host_lower == *expected,
            NetlocPatternKind::WildcardSuffix(suffix) => host_lower.ends_with(suffix.as_str()),
        }
    }

    /// Return ``True`` when the pattern represents a wildcard (``*`` or ``*.…``).
    const fn is_wildcard(&self) -> bool {
        matches!(self.kind, NetlocPatternKind::Any | NetlocPatternKind::WildcardSuffix(_))
    }

    /// Return ``True`` when the pattern matches any host (``*``).
    const fn is_any(&self) -> bool {
        matches!(self.kind, NetlocPatternKind::Any)
    }
}

pub fn build(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PathMatcher>()?;
    m.add_class::<NetlocMatcher>()?;
    m.add_class::<MatchKind>()?;
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

    #[test]
    fn type_tag_from_str() {
        assert!(matches!(TypeTag::from_str("str"), Ok(TypeTag::Str)));
        assert!(matches!(TypeTag::from_str("int"), Ok(TypeTag::Int)));
        assert!(matches!(TypeTag::from_str("float"), Ok(TypeTag::Float)));
        assert!(matches!(TypeTag::from_str("decimal"), Ok(TypeTag::Decimal)));
        assert!(matches!(TypeTag::from_str("uuid"), Ok(TypeTag::Uuid)));
        assert!(TypeTag::from_str("nope").is_err());
    }

    #[test]
    fn match_exact_str_param() {
        let m = matcher(&[(false, "users", ""), (true, "id", "str")]);
        let (kind, vals, matched, unmatched) = m.match_path_raw("/users/abc").unwrap();
        assert_eq!(kind, MatchKind::Exact);
        assert_eq!(vals, vec!["abc"]);
        assert_eq!(matched, "/users/abc");
        assert_eq!(unmatched, "");
    }

    #[test]
    fn match_partial_returns_unmatched_tail() {
        let m = matcher(&[(false, "api", "")]);
        let (kind, vals, matched, unmatched) = m.match_path_raw("/api/v1").unwrap();
        assert_eq!(kind, MatchKind::Partial);
        assert!(vals.is_empty());
        assert_eq!(matched, "/api");
        assert_eq!(unmatched, "/v1");
    }

    #[test]
    fn match_int_param_rejects_letters() {
        let m = matcher(&[(false, "id", ""), (true, "x", "int")]);
        assert!(m.match_path_raw("/id/abc").is_none());
        let (kind, vals, ..) = m.match_path_raw("/id/-12").unwrap();
        assert_eq!(kind, MatchKind::Exact);
        assert_eq!(vals, vec!["-12"]);
    }

    #[test]
    fn match_float_param_rejects_dot_only() {
        let m = matcher(&[(true, "x", "float")]);
        assert!(m.match_path_raw("/.").is_none());
        assert!(m.match_path_raw("/1.").is_none());
        let (_kind, vals, ..) = m.match_path_raw("/3.14").unwrap();
        assert_eq!(vals, vec!["3.14"]);
    }

    #[test]
    fn match_uuid_param_validates_dashes() {
        let m = matcher(&[(true, "x", "uuid")]);
        let id = "12345678-1234-1234-1234-123456789abc";
        let path = format!("/{id}");
        let (kind, vals, ..) = m.match_path_raw(&path).unwrap();
        assert_eq!(kind, MatchKind::Exact);
        assert_eq!(vals, vec![id]);
        assert!(m.match_path_raw("/not-a-uuid").is_none());
    }

    #[test]
    fn no_match_when_path_does_not_start_with_slash() {
        let m = matcher(&[(false, "users", "")]);
        assert!(m.match_path_raw("users").is_none());
    }

    #[test]
    fn netloc_exact_is_case_insensitive() {
        let n = NetlocMatcher::new("Example.com").unwrap();
        assert!(n.is_match("example.COM"));
        assert!(!n.is_match("foo.example.com"));
        assert!(!n.is_wildcard());
        assert!(!n.is_any());
    }

    #[test]
    fn netloc_wildcard_suffix() {
        let n = NetlocMatcher::new("*.example.com").unwrap();
        assert!(n.is_match("foo.example.com"));
        assert!(n.is_match("a.b.example.com"));
        assert!(!n.is_match("example.com"));
        assert!(n.is_wildcard());
        assert!(!n.is_any());
    }

    #[test]
    fn netloc_any_matches_everything() {
        let n = NetlocMatcher::new("*").unwrap();
        assert!(n.is_match("anything"));
        assert!(n.is_wildcard());
        assert!(n.is_any());
    }

    #[test]
    fn netloc_invalid_wildcard_pattern() {
        assert!(NetlocMatcher::new("foo*bar").is_err());
    }
}
