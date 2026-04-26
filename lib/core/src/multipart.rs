//! ASGI streaming multipart and urlencoded body parsers.
//!
//! Wraps [`multer`] for ``multipart/form-data`` (driven by an ASGI ``receive`` callable) and
//! [`form_urlencoded`] for ``application/x-www-form-urlencoded`` bodies. The Python surface
//! returns plain tuples/lists/bytes — no `PyO3` wrapper types — so callers can iterate the
//! result without Rust knowledge.

use bytes::Bytes;
use futures_util::stream::try_unfold;
use multer::Field;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyString, PyTuple};

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

/// Parsed value of a multipart form field.
enum FieldValue {
    Text(String),
    File {
        filename: String,
        content_type: String,
        data: Vec<u8>,
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
            Ok(PyTuple::new(
                py,
                [
                    filename.into_pyobject(py)?.into_any(),
                    content_type.into_pyobject(py)?.into_any(),
                    PyBytes::new(py, &data).into_any(),
                    header_list.into_any(),
                ],
            )?
            .into_any()
            .unbind())
        }
    }
}

/// Drain the multipart stream into an in-memory list of ``(name, value)`` pairs.
async fn collect_fields(
    receive: Py<PyAny>,
    boundary: String,
    max_files: usize,
    max_fields: usize,
) -> PyResult<Vec<(String, FieldValue)>> {
    let stream = body_stream(receive);
    let mut multipart = multer::Multipart::new(stream, boundary);

    let mut items: Vec<(String, FieldValue)> = Vec::new();
    let mut file_count: usize = 0;
    let mut field_count: usize = 0;

    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| PyValueError::new_err(e.to_string()))?
    {
        let meta = extract_field_metadata(&field);
        let data = field.bytes().await.map_err(|e| PyValueError::new_err(e.to_string()))?;

        if let Some(filename) = meta.filename {
            file_count += 1;
            if file_count > max_files {
                return Err(PyValueError::new_err(format!(
                    "Too many files. Maximum number of files is {max_files}."
                )));
            }
            items.push((
                meta.name,
                FieldValue::File {
                    filename,
                    content_type: meta.content_type,
                    data: data.to_vec(),
                    headers: meta.headers,
                },
            ));
        } else {
            field_count += 1;
            if field_count > max_fields {
                return Err(PyValueError::new_err(format!(
                    "Too many fields. Maximum number of fields is {max_fields}."
                )));
            }
            items.push((meta.name, FieldValue::Text(String::from_utf8_lossy(&data).into_owned())));
        }
    }

    Ok(items)
}

/// Parse ``multipart/form-data`` by streaming from an ASGI ``receive`` callable.
///
/// Returns a Python awaitable that resolves to
/// ``list[tuple[str, str | tuple[str, str, bytes, list[tuple[bytes, bytes]]]]]``.
///
/// Each item is ``(name, text_value)`` for plain fields or
/// ``(name, (filename, content_type, data, headers))`` for file uploads.
#[pyfunction]
#[pyo3(signature = (receive, boundary, *, max_files=1000, max_fields=1000))]
fn parse_multipart<'py>(
    py: Python<'py>,
    receive: Py<PyAny>,
    boundary: &str,
    max_files: usize,
    max_fields: usize,
) -> PyResult<Bound<'py, PyAny>> {
    let boundary = boundary.to_string();

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let items = collect_fields(receive, boundary, max_files, max_fields).await?;

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
    m.add_function(wrap_pyfunction!(parse_multipart, m)?)?;
    m.add_function(wrap_pyfunction!(parse_urlencoded, m)?)?;
    Ok(())
}
