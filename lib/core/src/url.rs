use pyo3::prelude::*;
use pyo3::types::PyTuple;

type MatchResult<'py> = Option<(i32, Bound<'py, PyTuple>, Option<&'py str>, Option<&'py str>)>;

#[derive(Clone)]
enum Segment {
    Constant(String),
    Parameter { type_tag: TypeTag },
}

#[derive(Clone, Copy)]
enum TypeTag {
    Str,
    Int,
    Float,
    Decimal,
    Uuid,
}

impl TypeTag {
    fn from_str(s: &str) -> Option<Self> {
        match s {
            "str" => Some(Self::Str),
            "int" => Some(Self::Int),
            "float" => Some(Self::Float),
            "decimal" => Some(Self::Decimal),
            "uuid" => Some(Self::Uuid),
            _ => None,
        }
    }
}

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
    /// Returns (match_type, param_values, matched, unmatched) or None.
    pub fn match_path_raw<'a>(
        &self,
        input: &'a str,
    ) -> Option<(i32, Vec<&'a str>, &'a str, &'a str)> {
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
                    let seg_len = remaining
                        .iter()
                        .position(|&b| b == b'/')
                        .unwrap_or(remaining.len());
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
        let match_type: i32 = if unmatched.is_empty() { 1 } else { 2 };

        Some((match_type, param_vals, matched, unmatched))
    }

    #[inline]
    fn is_valid_int(s: &[u8]) -> bool {
        let s = if !s.is_empty() && s[0] == b'-' {
            &s[1..]
        } else {
            s
        };
        !s.is_empty() && s.iter().all(|&b| b.is_ascii_digit())
    }

    #[inline]
    fn is_valid_float(s: &[u8]) -> bool {
        let s = if !s.is_empty() && s[0] == b'-' {
            &s[1..]
        } else {
            s
        };
        if s.is_empty() || !s[0].is_ascii_digit() {
            return false;
        }
        let digit_end = s
            .iter()
            .position(|b| !b.is_ascii_digit())
            .unwrap_or(s.len());
        if digit_end == s.len() {
            return true;
        }
        if s[digit_end] != b'.' {
            return false;
        }
        let rest = &s[digit_end + 1..];
        !rest.is_empty() && rest.iter().all(|b| b.is_ascii_digit())
    }

    #[inline]
    fn is_valid_uuid(s: &[u8]) -> bool {
        s.len() == 36
            && s[8] == b'-'
            && s[13] == b'-'
            && s[18] == b'-'
            && s[23] == b'-'
            && s.iter().enumerate().all(|(i, &c)| {
                i == 8
                    || i == 13
                    || i == 18
                    || i == 23
                    || c.is_ascii_digit()
                    || (b'a'..=b'f').contains(&c)
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
/// Returns match results as (match_type, param_values, matched, unmatched) where
/// param_values contains raw string slices — type conversion is done in Python
/// to avoid costly per-call object creation across the FFI boundary.
#[pymethods]
impl PathMatcher {
    #[new]
    #[pyo3(signature = (has_starting_slash, has_trailing_slash, segments))]
    fn new(
        has_starting_slash: bool,
        has_trailing_slash: bool,
        segments: Vec<(bool, String, String)>,
    ) -> Self {
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

        PathMatcher {
            has_starting_slash,
            has_trailing_slash,
            segments: parsed,
            param_count,
        }
    }

    /// Returns None on no-match, or a tuple:
    ///   (match_type: int, param_values: tuple[str, ...], matched: str|None, unmatched: str|None)
    ///
    /// match_type: 1=exact, 2=partial.
    /// param_values: raw strings in parameter declaration order (Python converts to typed values).
    fn match_path<'py>(&self, py: Python<'py>, input: &'py str) -> PyResult<MatchResult<'py>> {
        let raw = match self.match_path_raw(input) {
            Some(r) => r,
            None => return Ok(None),
        };

        let (match_type, param_vals, matched, unmatched) = raw;
        let vals_tuple = PyTuple::new(py, param_vals)?;
        let matched_opt = if matched.is_empty() {
            None
        } else {
            Some(matched)
        };
        let unmatched_opt = if unmatched.is_empty() {
            None
        } else {
            Some(unmatched)
        };

        Ok(Some((match_type, vals_tuple, matched_opt, unmatched_opt)))
    }
}

/// Pre-parsed netloc pattern for fast host matching.
///
/// Supports three pattern forms:
///   - `"*"` — matches any host.
///   - `"*.example.com"` — matches any subdomain of `example.com`.
///   - `"example.com"` — exact match only.
#[pyclass(skip_from_py_object)]
#[derive(Clone)]
pub struct NetlocMatcher {
    kind: NetlocPatternKind,
}

#[derive(Clone)]
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
        Ok(NetlocMatcher { kind })
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
    fn is_wildcard(&self) -> bool {
        matches!(self.kind, NetlocPatternKind::Any | NetlocPatternKind::WildcardSuffix(_))
    }

    /// Return ``True`` when the pattern matches any host (``*``).
    fn is_any(&self) -> bool {
        matches!(self.kind, NetlocPatternKind::Any)
    }
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "url")?;
    m.add_class::<PathMatcher>()?;
    m.add_class::<NetlocMatcher>()?;
    parent.add_submodule(&m)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item("flama._core.url", &m)?;
    Ok(())
}
