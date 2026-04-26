//! Fast JSON encoder for arbitrary Python values.
//!
//! Streams results into a [`Vec<u8>`] using `std::io::Write` and falls back to a curated
//! catalogue of "special" Python types ([`datetime`], [`uuid`], dataclasses, …) cached
//! once per interpreter via [`TypeCache`].

use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{
    PyBool, PyByteArray, PyBytes, PyDict, PyFloat, PyFrozenSet, PyInt, PyList, PySet, PyString, PyTuple, PyType,
};
use std::io::Write;

/// Lazily-resolved Python type handles used by [`JsonEncoder::encode_special`].
struct TypeCache {
    enum_type: Py<PyAny>,
    uuid_type: Py<PyAny>,
    timedelta_type: Py<PyAny>,
    datetime_type: Py<PyAny>,
    date_type: Py<PyAny>,
    time_type: Py<PyAny>,
    pathlike_type: Py<PyAny>,
    base_exc_type: Py<PyAny>,
    dc_is_dataclass: Py<PyAny>,
    dc_asdict: Py<PyAny>,
    flama_path: Option<Py<PyAny>>,
    flama_url: Option<Py<PyAny>>,
}

static TYPE_CACHE: PyOnceLock<TypeCache> = PyOnceLock::new();

impl TypeCache {
    fn new(py: Python<'_>) -> PyResult<Self> {
        let datetime_mod = py.import("datetime")?;
        let dataclasses_mod = py.import("dataclasses")?;

        let (flama_path, flama_url) = py.import("flama.url").map_or_else(
            |_| (None, None),
            |m| {
                (
                    m.getattr("Path").ok().map(Bound::unbind),
                    m.getattr("URL").ok().map(Bound::unbind),
                )
            },
        );

        Ok(Self {
            enum_type: py.import("enum")?.getattr("Enum")?.unbind(),
            uuid_type: py.import("uuid")?.getattr("UUID")?.unbind(),
            timedelta_type: datetime_mod.getattr("timedelta")?.unbind(),
            datetime_type: datetime_mod.getattr("datetime")?.unbind(),
            date_type: datetime_mod.getattr("date")?.unbind(),
            time_type: datetime_mod.getattr("time")?.unbind(),
            pathlike_type: py.import("os")?.getattr("PathLike")?.unbind(),
            base_exc_type: py.import("builtins")?.getattr("BaseException")?.unbind(),
            dc_is_dataclass: dataclasses_mod.getattr("is_dataclass")?.unbind(),
            dc_asdict: dataclasses_mod.getattr("asdict")?.unbind(),
            flama_path,
            flama_url,
        })
    }

    fn get(py: Python<'_>) -> PyResult<&Self> {
        TYPE_CACHE.get_or_try_init(py, || Self::new(py))
    }
}

/// Streaming JSON encoder writing UTF-8 bytes into a [`Vec<u8>`] buffer.
struct JsonEncoder {
    buf: Vec<u8>,
    sort_keys: bool,
    indent: Option<usize>,
    depth: usize,
    item_sep: &'static [u8],
    key_sep: &'static [u8],
}

impl JsonEncoder {
    fn new(sort_keys: bool, indent: Option<usize>, compact: bool) -> Self {
        let (item_sep, key_sep): (&[u8], &[u8]) = if compact {
            (b",", b":")
        } else if indent.is_some() {
            (b",", b": ")
        } else {
            (b", ", b": ")
        };
        Self {
            buf: Vec::with_capacity(256),
            sort_keys,
            indent,
            depth: 0,
            item_sep,
            key_sep,
        }
    }

    fn encode_value(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        if obj.is_none() {
            self.buf.extend_from_slice(b"null");
            return Ok(());
        }
        if obj.is_instance_of::<PyBool>() {
            self.buf
                .extend_from_slice(if obj.is_truthy()? { b"true" } else { b"false" });
            return Ok(());
        }
        if obj.is_instance_of::<PyString>() {
            self.encode_string(obj.cast::<PyString>()?.to_str()?);
            return Ok(());
        }
        if obj.is_instance_of::<PyInt>() {
            return self.encode_int(obj);
        }
        if obj.is_instance_of::<PyFloat>() {
            return self.encode_float(obj);
        }
        if obj.is_instance_of::<PyDict>() {
            return self.encode_dict(obj.cast::<PyDict>()?);
        }
        if obj.is_instance_of::<PyList>() || obj.is_instance_of::<PyTuple>() {
            return self.encode_seq(obj);
        }

        self.encode_special(obj)
    }

    fn encode_int(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        if let Ok(v) = obj.extract::<i64>() {
            // Writing into a Vec<u8> is infallible, so we ignore the Result.
            let _ = write!(&mut self.buf, "{v}");
        } else if let Ok(v) = obj.extract::<u64>() {
            let _ = write!(&mut self.buf, "{v}");
        } else {
            let s = obj.str()?;
            self.buf.extend_from_slice(s.to_str()?.as_bytes());
        }
        Ok(())
    }

    fn encode_float(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        let val: f64 = obj.extract()?;
        if val.is_nan() || val.is_infinite() {
            return Err(PyValueError::new_err(
                "Out of range float values are not JSON compliant",
            ));
        }
        let repr = obj.repr()?;
        self.buf.extend_from_slice(repr.to_str()?.as_bytes());
        Ok(())
    }

    fn encode_string(&mut self, s: &str) {
        self.buf.push(b'"');
        let bytes = s.as_bytes();
        let mut start = 0;
        for (i, &b) in bytes.iter().enumerate() {
            let replacement: &[u8] = match b {
                b'"' => b"\\\"",
                b'\\' => b"\\\\",
                b'\n' => b"\\n",
                b'\r' => b"\\r",
                b'\t' => b"\\t",
                0x08 => b"\\b",
                0x0C => b"\\f",
                b if b < 0x20 => {
                    self.buf.extend_from_slice(&bytes[start..i]);
                    let _ = write!(&mut self.buf, "\\u{b:04x}");
                    start = i + 1;
                    continue;
                }
                _ => continue,
            };
            self.buf.extend_from_slice(&bytes[start..i]);
            self.buf.extend_from_slice(replacement);
            start = i + 1;
        }
        self.buf.extend_from_slice(&bytes[start..]);
        self.buf.push(b'"');
    }

    fn encode_key(&mut self, key: &Bound<'_, PyAny>) -> PyResult<()> {
        if key.is_instance_of::<PyString>() {
            self.encode_string(key.cast::<PyString>()?.to_str()?);
        } else if key.is_instance_of::<PyBool>() {
            self.encode_string(if key.is_truthy()? { "true" } else { "false" });
        } else if key.is_instance_of::<PyInt>() {
            let s = key.str()?;
            self.encode_string(s.to_str()?);
        } else if key.is_instance_of::<PyFloat>() {
            let val: f64 = key.extract()?;
            if val.is_nan() || val.is_infinite() {
                return Err(PyValueError::new_err(
                    "Out of range float values are not JSON compliant",
                ));
            }
            self.encode_string(key.repr()?.to_str()?);
        } else if key.is_none() {
            self.encode_string("null");
        } else {
            return Err(PyTypeError::new_err(format!(
                "keys must be str, int, float, bool or None, not {}",
                key.get_type().qualname()?
            )));
        }
        Ok(())
    }

    fn encode_dict(&mut self, dict: &Bound<'_, PyDict>) -> PyResult<()> {
        self.buf.push(b'{');
        if dict.is_empty() {
            self.buf.push(b'}');
            return Ok(());
        }

        self.depth += 1;

        if self.sort_keys {
            let mut items: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)> = dict.iter().collect();
            items.sort_by(|(a, _), (b, _)| {
                let ak = a.str().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
                let bk = b.str().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
                ak.cmp(&bk)
            });
            for (i, (k, v)) in items.iter().enumerate() {
                self.write_item_sep(i > 0);
                self.encode_key(k)?;
                self.write_kv_sep();
                self.encode_value(v)?;
            }
        } else {
            for (i, (k, v)) in dict.iter().enumerate() {
                self.write_item_sep(i > 0);
                self.encode_key(&k)?;
                self.write_kv_sep();
                self.encode_value(&v)?;
            }
        }

        self.depth -= 1;
        self.write_newline_indent();
        self.buf.push(b'}');
        Ok(())
    }

    fn encode_seq(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        self.buf.push(b'[');
        let iter = obj.try_iter()?;
        self.depth += 1;
        let mut count = 0;
        for item in iter {
            self.write_item_sep(count > 0);
            self.encode_value(&item?)?;
            count += 1;
        }
        self.depth -= 1;
        if count > 0 {
            self.write_newline_indent();
        }
        self.buf.push(b']');
        Ok(())
    }

    fn encode_special(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        let py = obj.py();
        let types = TypeCache::get(py)?;

        if obj.is_instance_of::<PyBytes>() {
            let s = std::str::from_utf8(obj.cast::<PyBytes>()?.as_bytes())
                .map_err(|e| PyValueError::new_err(format!("bytes is not valid UTF-8: {e}")))?;
            self.encode_string(s);
            return Ok(());
        }
        if obj.is_instance_of::<PyByteArray>() {
            let decoded: String = obj.call_method1("decode", ("utf-8",))?.extract()?;
            self.encode_string(&decoded);
            return Ok(());
        }

        if obj.is_instance_of::<PySet>() || obj.is_instance_of::<PyFrozenSet>() {
            return self.encode_seq(obj);
        }

        if obj.is_instance(types.enum_type.bind(py))? {
            let value = obj.getattr("value")?;
            return self.encode_value(&value);
        }

        if obj.is_instance(types.uuid_type.bind(py))? {
            self.encode_string(obj.str()?.to_str()?);
            return Ok(());
        }

        if obj.is_instance(types.timedelta_type.bind(py))? {
            let total: f64 = obj.call_method0("total_seconds")?.extract()?;
            self.encode_string(&format_timedelta(total));
            return Ok(());
        }

        if obj.is_instance(types.datetime_type.bind(py))?
            || obj.is_instance(types.date_type.bind(py))?
            || obj.is_instance(types.time_type.bind(py))?
        {
            let iso: String = obj.call_method0("isoformat")?.extract()?;
            self.encode_string(&iso);
            return Ok(());
        }

        if obj.is_instance(types.pathlike_type.bind(py))? {
            self.encode_string(obj.str()?.to_str()?);
            return Ok(());
        }

        if let Some(ref t) = types.flama_path {
            if obj.is_instance(t.bind(py))? {
                self.encode_string(obj.str()?.to_str()?);
                return Ok(());
            }
        }
        if let Some(ref t) = types.flama_url {
            if obj.is_instance(t.bind(py))? {
                self.encode_string(obj.str()?.to_str()?);
                return Ok(());
            }
        }

        if let Ok(typ) = obj.cast::<PyType>() {
            if typ.is_subclass(types.base_exc_type.bind(py))? {
                let name: String = obj.getattr("__name__")?.extract()?;
                self.encode_string(&name);
                return Ok(());
            }
        }

        if obj.is_instance(types.base_exc_type.bind(py))? {
            self.encode_string(obj.repr()?.to_str()?);
            return Ok(());
        }

        if types.dc_is_dataclass.bind(py).call1((obj,))?.is_truthy()? && !obj.is_instance_of::<PyType>() {
            let dict = types.dc_asdict.bind(py).call1((obj,))?;
            return self.encode_value(&dict);
        }

        let type_name: String = obj.get_type().getattr("__name__")?.extract()?;
        Err(PyTypeError::new_err(format!(
            "Object of type {type_name} is not JSON serializable",
        )))
    }

    fn write_item_sep(&mut self, comma: bool) {
        if comma {
            self.buf.extend_from_slice(self.item_sep);
        }
        self.write_newline_indent();
    }

    fn write_kv_sep(&mut self) {
        self.buf.extend_from_slice(self.key_sep);
    }

    fn write_newline_indent(&mut self) {
        if let Some(n) = self.indent {
            self.buf.push(b'\n');
            let spaces = self.depth * n;
            self.buf.resize(self.buf.len() + spaces, b' ');
        }
    }
}

/// Format a number of seconds (possibly fractional) as an ISO-8601 duration like ``P1DT2H3M4S``.
///
/// Truncations to integer days/hours/minutes are intentional: sub-units of the smallest non-zero
/// component are emitted as the fractional part of the seconds field, which is how `timedelta`
/// values are normalised for JSON output.
fn format_timedelta(total: f64) -> String {
    let mins = total.div_euclid(60.0);
    let secs = total.rem_euclid(60.0);
    let hrs = mins.div_euclid(60.0);
    let mins = mins.rem_euclid(60.0);
    let days = hrs.div_euclid(24.0);
    let hrs = hrs.rem_euclid(24.0);

    #[allow(clippy::cast_possible_truncation)]
    let days = days as i64;
    #[allow(clippy::cast_possible_truncation)]
    let hrs = hrs as i64;
    #[allow(clippy::cast_possible_truncation)]
    let mins = mins as i64;
    let secs = (secs * 1_000_000.0).round() / 1_000_000.0;

    let mut r = String::from("P");
    if days != 0 {
        r.push_str(format!("{days:02}").trim_start_matches('0'));
        r.push('D');
    }
    if hrs != 0 {
        r.push_str(format!("{hrs:02}").trim_start_matches('0'));
        r.push('H');
    }
    if mins != 0 {
        r.push_str(format!("{mins:02}").trim_start_matches('0'));
        r.push('M');
    }
    if secs != 0.0 {
        r.push_str(format!("{secs:.6}").trim_matches('0'));
        r.push('S');
    }
    r
}

#[pyfunction]
#[pyo3(signature = (content, *, sort_keys=false, indent=None, compact=false))]
fn encode_json<'py>(
    py: Python<'py>,
    content: &Bound<'py, PyAny>,
    sort_keys: bool,
    indent: Option<usize>,
    compact: bool,
) -> PyResult<Bound<'py, PyBytes>> {
    let mut enc = JsonEncoder::new(sort_keys, indent, compact);
    enc.encode_value(content)?;
    Ok(PyBytes::new(py, &enc.buf))
}

pub fn build(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_json, m)?)?;
    Ok(())
}

#[cfg(test)]
#[allow(clippy::suboptimal_flops)]
mod tests {
    use super::*;

    #[test]
    fn timedelta_zero_is_bare_p() {
        assert_eq!(format_timedelta(0.0), "P");
    }

    #[test]
    fn timedelta_subsecond() {
        // 0.5 seconds -> "P.5S" after trimming trailing zeros.
        assert_eq!(format_timedelta(0.5), "P.5S");
    }

    #[test]
    fn timedelta_hms_only() {
        // 1 hour 2 minutes 3 seconds.
        assert_eq!(format_timedelta(3600.0 + 120.0 + 3.0), "P1H2M3.S");
    }

    #[test]
    fn timedelta_full_hms_days() {
        // 2 days, 3 hours, 4 minutes, 5 seconds.
        let total = 2.0 * 86_400.0 + 3.0 * 3600.0 + 4.0 * 60.0 + 5.0;
        assert_eq!(format_timedelta(total), "P2D3H4M5.S");
    }

    #[test]
    fn timedelta_negative_uses_euclid_normalisation() {
        // div_euclid/rem_euclid keep all components non-negative; we just verify it does
        // not panic and emits something sane.
        let s = format_timedelta(-1.0);
        assert!(s.starts_with('P'));
    }
}
