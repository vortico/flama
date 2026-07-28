//! ASGI streaming multipart and urlencoded body parsers.
//!
//! Wraps [`multer`] for ``multipart/form-data`` (driven by an ASGI ``receive`` callable) and
//! [`form_urlencoded`] for ``application/x-www-form-urlencoded`` bodies. The Python surface
//! returns plain tuples/lists/bytes — no `PyO3` wrapper types — so callers can iterate the
//! result without Rust knowledge.

use std::path::PathBuf;

use bytes::Bytes;
use futures_util::stream::try_unfold;
use multer::Field;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyString, PyTuple};
use tokio::io::AsyncWriteExt;

pyo3::create_exception!(
    multipart,
    PayloadTooLarge,
    PyValueError,
    "Raised when a multipart body exceeds one of the configured size or count limits."
);

/// Build a ``Stream`` that pulls body chunks from an ASGI ``receive`` callable.
///
/// Uses [`futures_util::stream::try_unfold`] so that each poll drives the ASGI
/// receive→await→extract cycle inline — no spawned background task, preserving
/// the pyo3-async-runtimes task-local context (Python event loop).
///
/// The state is `Option<Py<PyAny>>`: ``Some(receive)`` while there are more
/// chunks, ``None`` once the final chunk has been yielded.
fn body_stream(receive: Py<PyAny>) -> impl futures_util::Stream<Item = Result<Bytes, std::io::Error>> + Send + 'static {
    try_unfold(Some(receive), |state| async move {
        let Some(receive) = state else { return Ok(None) };

        let coro: Py<PyAny> =
            Python::attach(|py| receive.call0(py)).map_err(|e| std::io::Error::other(e.to_string()))?;

        let future = Python::attach(|py| pyo3_async_runtimes::tokio::into_future(coro.into_bound(py)))
            .map_err(|e| std::io::Error::other(e.to_string()))?;

        let message: Py<PyAny> = future.await.map_err(|e| std::io::Error::other(e.to_string()))?;

        let (chunk, more) = Python::attach(|py| -> PyResult<(Vec<u8>, bool)> {
            let msg = message.bind(py).cast::<PyDict>()?;

            let msg_type: String = msg
                .get_item("type")?
                .ok_or_else(|| PyValueError::new_err("ASGI message missing 'type'"))?
                .extract()?;

            if msg_type == "http.disconnect" {
                return Err(PyValueError::new_err("Client disconnected"));
            }

            let chunk: Vec<u8> = match msg.get_item("body")? {
                Some(v) => v.cast::<PyBytes>()?.as_bytes().to_vec(),
                None => Vec::new(),
            };

            let more: bool = msg
                .get_item("more_body")?
                .map(|v| v.extract::<bool>())
                .transpose()?
                .unwrap_or(false);

            Ok((chunk, more))
        })
        .map_err(|e| std::io::Error::other(e.to_string()))?;

        if chunk.is_empty() && !more {
            return Ok(None);
        }

        let bytes = Bytes::from(chunk);
        let next_state = if more { Some(receive) } else { None };
        Ok(Some((bytes, next_state)))
    })
}

/// Payload of an uploaded file, kept in memory while small and spooled to disk once it grows past
/// the configured threshold so that a large upload never has to fit in RAM.
#[derive(Debug)]
enum FileData {
    Memory(Vec<u8>),
    Spooled(PathBuf),
}

/// Parsed value of a multipart form field.
enum FieldValue {
    Text(String),
    File {
        filename: String,
        content_type: String,
        data: FileData,
        headers: Vec<(Vec<u8>, Vec<u8>)>,
    },
}

/// Field-level metadata extracted from a [`Field`] before its body is consumed.
struct FieldMeta {
    name: String,
    filename: Option<String>,
    content_type: String,
    headers: Vec<(Vec<u8>, Vec<u8>)>,
}

/// Read the synchronously-available metadata from a multipart [`Field`].
fn extract_field_metadata(field: &Field<'static>) -> FieldMeta {
    let name = field.name().unwrap_or("").to_string();
    let filename = field.file_name().map(ToOwned::to_owned);
    let content_type = field.content_type().map_or_else(
        || {
            if filename.is_some() {
                "application/octet-stream".to_string()
            } else {
                String::new()
            }
        },
        ToString::to_string,
    );
    let headers: Vec<(Vec<u8>, Vec<u8>)> = field
        .headers()
        .iter()
        .map(|(k, v)| (k.as_str().as_bytes().to_vec(), v.as_bytes().to_vec()))
        .collect();

    FieldMeta {
        name,
        filename,
        content_type,
        headers,
    }
}

/// Limits applied while draining a multipart body.
#[derive(Clone, Copy)]
struct Limits {
    max_files: usize,
    max_fields: usize,
    spool_threshold: u64,
    max_file_size: Option<u64>,
    max_body_size: Option<u64>,
}

/// Drain a single field, keeping it in memory until it exceeds `spool_threshold` and streaming the
/// remainder to a temporary file after that.
///
/// `body_read` accumulates across all fields so that the total body limit spans the whole request.
async fn read_field(field: &mut Field<'static>, limits: Limits, body_read: &mut u64) -> PyResult<FileData> {
    let mut spool: Option<(tokio::fs::File, PathBuf)> = None;

    match drain_field(field, limits, body_read, &mut spool).await {
        Ok(data) => Ok(data),
        Err(e) => {
            if let Some((_, path)) = spool {
                let _ = tokio::fs::remove_file(&path).await;
            }
            Err(e)
        }
    }
}

/// Read every chunk of a field, spooling to `spool` once the threshold is crossed.
///
/// Kept separate from [`read_field`] so that the caller still owns the spool handle on failure and
/// can unlink a partially written file. `spool` is left populated unless the field is read in full,
/// which is what makes that cleanup possible.
///
/// Size limits are checked per chunk, so an oversized payload is rejected as soon as it crosses the
/// limit rather than after the whole of it has been buffered.
async fn drain_field(
    field: &mut Field<'static>,
    limits: Limits,
    body_read: &mut u64,
    spool: &mut Option<(tokio::fs::File, PathBuf)>,
) -> PyResult<FileData> {
    let mut buffer: Vec<u8> = Vec::new();
    let mut field_read: u64 = 0;

    while let Some(chunk) = field.chunk().await.map_err(|e| PyValueError::new_err(e.to_string()))? {
        field_read += chunk.len() as u64;
        *body_read += chunk.len() as u64;

        if let Some(max) = limits.max_file_size {
            if field_read > max {
                return Err(PayloadTooLarge::new_err(format!(
                    "File too large. Maximum size per file is {max} bytes."
                )));
            }
        }

        if let Some(max) = limits.max_body_size {
            if *body_read > max {
                return Err(PayloadTooLarge::new_err(format!(
                    "Request body too large. Maximum size is {max} bytes."
                )));
            }
        }

        if let Some((file, _)) = spool.as_mut() {
            file.write_all(&chunk).await?;
        } else if field_read > limits.spool_threshold {
            // `keep` detaches the file from its guard, so it outlives this scope and its removal
            // becomes the caller's responsibility.
            let (std_file, path) = tempfile::NamedTempFile::new()
                .map_err(|e| PyValueError::new_err(e.to_string()))?
                .keep()
                .map_err(|e| PyValueError::new_err(e.to_string()))?;
            let mut file = tokio::fs::File::from_std(std_file);
            file.write_all(&buffer).await?;
            file.write_all(&chunk).await?;
            buffer = Vec::new();
            *spool = Some((file, path));
        } else {
            buffer.extend_from_slice(&chunk);
        }
    }

    // Flush before taking ownership: a failure here must leave `spool` populated so the caller still
    // knows there is a file to remove.
    if let Some((file, _)) = spool.as_mut() {
        file.flush().await?;
    }

    Ok(match spool.take() {
        Some((_, path)) => FileData::Spooled(path),
        None => FileData::Memory(buffer),
    })
}

/// Remove every temporary file already spooled for the given fields.
///
/// Used on the error paths so that a rejected request does not leave orphaned files behind: Python
/// never receives these values and therefore never gets the chance to clean them up itself.
async fn discard_spooled(items: &[(String, FieldValue)]) {
    for (_, value) in items {
        if let FieldValue::File {
            data: FileData::Spooled(path),
            ..
        } = value
        {
            let _ = tokio::fs::remove_file(path).await;
        }
    }
}

/// Convert a [`FieldValue`] into the matching Python object.
fn build_python_value(py: Python<'_>, value: FieldValue) -> PyResult<Py<PyAny>> {
    match value {
        FieldValue::Text(text) => Ok(text.into_pyobject(py)?.into_any().unbind()),
        FieldValue::File {
            filename,
            content_type,
            data,
            headers,
        } => {
            let header_list = PyList::empty(py);
            for (k, v) in headers {
                header_list.append(PyTuple::new(
                    py,
                    [PyBytes::new(py, &k).into_any(), PyBytes::new(py, &v).into_any()],
                )?)?;
            }

            // Exactly one of `data`/`path` carries the payload: a spooled upload reports its path and
            // empty bytes, and Python takes over responsibility for unlinking the file.
            let (payload, path) = match data {
                FileData::Memory(bytes) => (PyBytes::new(py, &bytes).into_any(), py.None().into_bound(py)),
                FileData::Spooled(path) => (
                    PyBytes::new(py, &[]).into_any(),
                    PyString::new(py, &path.to_string_lossy()).into_any(),
                ),
            };

            Ok(PyTuple::new(
                py,
                [
                    filename.into_pyobject(py)?.into_any(),
                    content_type.into_pyobject(py)?.into_any(),
                    payload,
                    path,
                    header_list.into_any(),
                ],
            )?
            .into_any()
            .unbind())
        }
    }
}

/// Drain the multipart stream into an in-memory list of ``(name, value)`` pairs.
async fn collect_fields(receive: Py<PyAny>, boundary: String, limits: Limits) -> PyResult<Vec<(String, FieldValue)>> {
    let mut items: Vec<(String, FieldValue)> = Vec::new();

    match drain_fields(receive, boundary, limits, &mut items).await {
        Ok(()) => Ok(items),
        Err(e) => {
            discard_spooled(&items).await;
            Err(e)
        }
    }
}

/// Drain every field of the multipart stream into `items`.
///
/// Kept separate from [`collect_fields`] so that the caller still owns the partially filled `items`
/// on failure and can unlink whatever was already spooled to disk.
async fn drain_fields(
    receive: Py<PyAny>,
    boundary: String,
    limits: Limits,
    items: &mut Vec<(String, FieldValue)>,
) -> PyResult<()> {
    let stream = body_stream(receive);
    let mut multipart = multer::Multipart::new(stream, boundary);

    let mut file_count: usize = 0;
    let mut field_count: usize = 0;
    let mut body_read: u64 = 0;

    while let Some(mut field) = multipart
        .next_field()
        .await
        .map_err(|e| PyValueError::new_err(e.to_string()))?
    {
        let meta = extract_field_metadata(&field);

        if let Some(filename) = meta.filename {
            file_count += 1;
            if file_count > limits.max_files {
                return Err(PayloadTooLarge::new_err(format!(
                    "Too many files. Maximum number of files is {}.",
                    limits.max_files
                )));
            }

            let data = read_field(&mut field, limits, &mut body_read).await?;
            items.push((
                meta.name,
                FieldValue::File {
                    filename,
                    content_type: meta.content_type,
                    data,
                    headers: meta.headers,
                },
            ));
        } else {
            field_count += 1;
            if field_count > limits.max_fields {
                return Err(PayloadTooLarge::new_err(format!(
                    "Too many fields. Maximum number of fields is {}.",
                    limits.max_fields
                )));
            }

            // Text fields are bounded by `max_fields` and are never spooled, so the threshold is
            // disabled for them and the value is decoded straight from memory.
            let text_limits = Limits {
                spool_threshold: u64::MAX,
                ..limits
            };
            match read_field(&mut field, text_limits, &mut body_read).await? {
                FileData::Memory(data) => {
                    items.push((meta.name, FieldValue::Text(String::from_utf8_lossy(&data).into_owned())));
                }
                FileData::Spooled(path) => {
                    let _ = tokio::fs::remove_file(&path).await;
                    return Err(PyValueError::new_err("Unexpected spooled text field."));
                }
            }
        }
    }

    Ok(())
}

/// Parse ``multipart/form-data`` by streaming from an ASGI ``receive`` callable.
///
/// Returns a Python awaitable that resolves to
/// ``list[tuple[str, str | tuple[str, str, bytes, str | None, list[tuple[bytes, bytes]]]]]``.
///
/// Each item is ``(name, text_value)`` for plain fields or
/// ``(name, (filename, content_type, data, path, headers))`` for file uploads. A file kept in memory
/// reports its bytes in ``data`` and ``None`` in ``path``; one spooled to disk reports empty ``data``
/// and the temporary file path, which the caller owns and must unlink.
#[pyfunction]
#[pyo3(signature = (
    receive,
    boundary,
    *,
    max_files=1000,
    max_fields=1000,
    spool_threshold=1024 * 1024,
    max_file_size=None,
    max_body_size=None,
))]
fn parse_multipart<'py>(
    py: Python<'py>,
    receive: Py<PyAny>,
    boundary: &str,
    max_files: usize,
    max_fields: usize,
    spool_threshold: u64,
    max_file_size: Option<u64>,
    max_body_size: Option<u64>,
) -> PyResult<Bound<'py, PyAny>> {
    let boundary = boundary.to_string();
    let limits = Limits {
        max_files,
        max_fields,
        spool_threshold,
        max_file_size,
        max_body_size,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let items = collect_fields(receive, boundary, limits).await?;

        Python::attach(|py| -> PyResult<Py<PyAny>> {
            let list = PyList::empty(py);
            for (name, value) in items {
                let py_value = build_python_value(py, value)?;
                list.append(PyTuple::new(
                    py,
                    [PyString::new(py, &name).into_any(), py_value.into_bound(py).into_any()],
                )?)?;
            }
            Ok(list.into_any().unbind())
        })
    })
}

/// Parse ``application/x-www-form-urlencoded`` body bytes.
///
/// Returns ``list[tuple[str, str]]``.
#[pyfunction]
fn parse_urlencoded<'py>(py: Python<'py>, body: &Bound<'py, PyBytes>) -> PyResult<Bound<'py, PyList>> {
    let pairs: Vec<(String, String)> = form_urlencoded::parse(body.as_bytes())
        .map(|(k, v)| (k.into_owned(), v.into_owned()))
        .collect();

    let list = PyList::empty(py);
    for (k, v) in pairs {
        list.append(PyTuple::new(
            py,
            [PyString::new(py, &k).into_any(), PyString::new(py, &v).into_any()],
        )?)?;
    }
    Ok(list)
}

pub fn build(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("PayloadTooLarge", m.py().get_type::<PayloadTooLarge>())?;
    m.add_function(wrap_pyfunction!(parse_multipart, m)?)?;
    m.add_function(wrap_pyfunction!(parse_urlencoded, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const BOUNDARY: &str = "X";

    /// Serialises the tests that repoint the process-wide temp directory.
    static TEMP_DIR_GUARD: std::sync::Mutex<()> = std::sync::Mutex::new(());

    /// Redirect `tempfile` to a private directory for the duration of a test.
    ///
    /// Spooling targets `std::env::temp_dir()`, which is shared with every other process on the
    /// machine, so counting entries there to detect a leak would be unreliable. Holding the guard
    /// keeps the two tests that do this from racing each other.
    struct IsolatedTempDir {
        _guard: std::sync::MutexGuard<'static, ()>,
        previous: Option<std::ffi::OsString>,
        dir: tempfile::TempDir,
    }

    impl IsolatedTempDir {
        fn new() -> Self {
            let guard = TEMP_DIR_GUARD.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
            let dir = tempfile::TempDir::new().unwrap();
            let previous = std::env::var_os("TMPDIR");
            std::env::set_var("TMPDIR", dir.path());
            Self {
                _guard: guard,
                previous,
                dir,
            }
        }

        fn len(&self) -> usize {
            std::fs::read_dir(self.dir.path()).unwrap().count()
        }
    }

    impl Drop for IsolatedTempDir {
        fn drop(&mut self) {
            match &self.previous {
                Some(value) => std::env::set_var("TMPDIR", value),
                None => std::env::remove_var("TMPDIR"),
            }
        }
    }

    fn limits(spool_threshold: u64, max_file_size: Option<u64>, max_body_size: Option<u64>) -> Limits {
        Limits {
            max_files: 1000,
            max_fields: 1000,
            spool_threshold,
            max_file_size,
            max_body_size,
        }
    }

    /// Build a multipart stream carrying one file part per `(name, contents)` pair.
    fn multipart(parts: &[(&str, &[u8])]) -> multer::Multipart<'static> {
        let mut body: Vec<u8> = Vec::new();
        for (name, contents) in parts {
            body.extend_from_slice(format!("--{BOUNDARY}\r\n").as_bytes());
            body.extend_from_slice(
                format!("Content-Disposition: form-data; name=\"{name}\"; filename=\"{name}.bin\"\r\n\r\n").as_bytes(),
            );
            body.extend_from_slice(contents);
            body.extend_from_slice(b"\r\n");
        }
        body.extend_from_slice(format!("--{BOUNDARY}--\r\n").as_bytes());

        let stream = futures_util::stream::iter(vec![Ok::<_, std::io::Error>(Bytes::from(body))]);
        multer::Multipart::new(stream, BOUNDARY)
    }

    #[tokio::test]
    async fn small_field_is_kept_in_memory() {
        let mut multipart = multipart(&[("f", b"hello")]);
        let mut field = multipart.next_field().await.unwrap().unwrap();
        let mut body_read = 0;

        let data = read_field(&mut field, limits(1024, None, None), &mut body_read)
            .await
            .unwrap();

        assert!(matches!(data, FileData::Memory(ref b) if b == b"hello"));
        assert_eq!(body_read, 5);
    }

    #[tokio::test]
    async fn large_field_spools_to_disk_with_full_contents() {
        let _temp = IsolatedTempDir::new();
        let contents = vec![b'x'; 4096];
        let mut multipart = multipart(&[("f", &contents)]);
        let mut field = multipart.next_field().await.unwrap().unwrap();
        let mut body_read = 0;

        let data = read_field(&mut field, limits(16, None, None), &mut body_read)
            .await
            .unwrap();

        let FileData::Spooled(path) = data else {
            panic!("expected the field to spool to disk");
        };
        assert_eq!(std::fs::read(&path).unwrap(), contents);
        assert_eq!(body_read, 4096);
        std::fs::remove_file(&path).unwrap();
    }

    // Only the failure itself is asserted here: reading the message out of a `PyErr` would require an
    // initialised interpreter, so the wording is covered from the Python suite instead.

    #[tokio::test]
    // `temp` must live to the end of the scope: it holds the guard and restores `TMPDIR` on drop.
    #[allow(clippy::significant_drop_tightening)]
    async fn field_over_max_file_size_is_rejected_without_leaving_a_file() {
        let temp = IsolatedTempDir::new();
        let mut multipart = multipart(&[("f", &vec![b'x'; 4096])]);
        let mut field = multipart.next_field().await.unwrap().unwrap();
        let mut body_read = 0;

        let result = read_field(&mut field, limits(16, Some(64), None), &mut body_read).await;

        assert!(result.is_err());
        assert_eq!(temp.len(), 0, "the partial spool file must be removed");
    }

    #[tokio::test]
    // `temp` must live to the end of the scope: it holds the guard and restores `TMPDIR` on drop.
    #[allow(clippy::significant_drop_tightening)]
    async fn body_over_max_body_size_is_rejected_without_leaving_a_file() {
        let temp = IsolatedTempDir::new();
        let mut multipart = multipart(&[("f", &vec![b'x'; 4096])]);
        let mut field = multipart.next_field().await.unwrap().unwrap();
        // Pretend earlier fields already consumed most of the allowance, so the limit trips only once
        // the field has started spooling.
        let mut body_read = 900;

        let result = read_field(&mut field, limits(16, None, Some(1000)), &mut body_read).await;

        assert!(result.is_err());
        assert_eq!(temp.len(), 0, "the partial spool file must be removed");
    }

    #[tokio::test]
    async fn body_over_max_body_size_is_rejected_before_spooling() {
        let mut multipart = multipart(&[("f", b"0123456789")]);
        let mut field = multipart.next_field().await.unwrap().unwrap();
        let mut body_read = 95;

        let result = read_field(&mut field, limits(1024, None, Some(100)), &mut body_read).await;

        assert!(result.is_err());
    }

    #[tokio::test]
    async fn discard_spooled_removes_every_temporary_file() {
        let file = tempfile::NamedTempFile::new().unwrap();
        let (_, path) = file.keep().unwrap();
        let items = vec![(
            "f".to_owned(),
            FieldValue::File {
                filename: "f.bin".to_owned(),
                content_type: "application/octet-stream".to_owned(),
                data: FileData::Spooled(path.clone()),
                headers: vec![],
            },
        )];

        assert!(path.exists());

        discard_spooled(&items).await;

        assert!(!path.exists());
    }
}
