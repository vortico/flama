use pyo3::prelude::*;
use pyo3::types::PyBytes;
use std::io::Write;

/// Streaming gzip compressor backed by flate2.
///
/// Compressed output is available after each `compress` call, making this
/// suitable for chunked HTTP responses.
#[pyclass]
pub struct GzipCompressor {
    inner: Option<flate2::write::GzEncoder<Vec<u8>>>,
}

#[pymethods]
impl GzipCompressor {
    #[new]
    #[pyo3(signature = (level=9))]
    fn new(level: u32) -> Self {
        GzipCompressor {
            inner: Some(flate2::write::GzEncoder::new(
                Vec::new(),
                flate2::Compression::new(level),
            )),
        }
    }

    /// Compress a chunk of data.
    ///
    /// When *finish* is true the gzip stream is finalised and no further
    /// calls are allowed.  Intermediate calls flush and return whatever
    /// compressed bytes are available so far.
    fn compress<'py>(
        &mut self,
        py: Python<'py>,
        data: &[u8],
        finish: bool,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let encoder = self.inner.as_mut().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("compressor already finished")
        })?;

        encoder.write_all(data).map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("gzip compression error: {e}"))
        })?;

        if finish {
            let encoder = self.inner.take().unwrap();
            let buf = encoder.finish().map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!("gzip finish error: {e}"))
            })?;
            Ok(PyBytes::new(py, &buf))
        } else {
            encoder.flush().map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!("gzip flush error: {e}"))
            })?;
            let buf = encoder.get_mut();
            let drained = std::mem::take(buf);
            Ok(PyBytes::new(py, &drained))
        }
    }
}

/// Brotli compressor.
///
/// Input chunks are accumulated internally; the actual brotli compression
/// is performed in a single pass when *finish* is true.  This is the
/// optimal strategy for typical HTTP responses that arrive in one or two
/// body chunks.
#[pyclass]
pub struct BrotliCompressor {
    quality: u32,
    lgwin: u32,
    buffer: Vec<u8>,
    finished: bool,
}

#[pymethods]
impl BrotliCompressor {
    #[new]
    #[pyo3(signature = (quality=4, lgwin=22))]
    fn new(quality: u32, lgwin: u32) -> Self {
        BrotliCompressor {
            quality,
            lgwin,
            buffer: Vec::new(),
            finished: false,
        }
    }

    /// Compress a chunk of data.
    ///
    /// Intermediate calls buffer the input and return empty bytes.  When
    /// *finish* is true the accumulated input is brotli-compressed and
    /// returned in one piece.
    fn compress<'py>(
        &mut self,
        py: Python<'py>,
        data: &[u8],
        finish: bool,
    ) -> PyResult<Bound<'py, PyBytes>> {
        if self.finished {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "compressor already finished",
            ));
        }

        self.buffer.extend_from_slice(data);

        if finish {
            self.finished = true;
            let mut output = Vec::new();
            {
                let mut writer =
                    brotli::CompressorWriter::new(&mut output, 4096, self.quality, self.lgwin);
                writer.write_all(&self.buffer).map_err(|e| {
                    pyo3::exceptions::PyRuntimeError::new_err(format!(
                        "brotli compression error: {e}"
                    ))
                })?;
            }
            self.buffer.clear();
            Ok(PyBytes::new(py, &output))
        } else {
            Ok(PyBytes::new(py, b""))
        }
    }
}

// ---------------------------------------------------------------------------
// One-shot compress / decompress helpers for serialization
// ---------------------------------------------------------------------------

#[pyfunction]
fn compress_bz2<'py>(py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    use bzip2::read::BzEncoder;
    use bzip2::Compression;
    use std::io::Read;

    let mut encoder = BzEncoder::new(data, Compression::best());
    let mut out = Vec::new();
    encoder.read_to_end(&mut out).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("bz2 compress error: {e}"))
    })?;
    Ok(PyBytes::new(py, &out))
}

#[pyfunction]
fn decompress_bz2<'py>(py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    use bzip2::read::BzDecoder;
    use std::io::Read;

    let mut decoder = BzDecoder::new(data);
    let mut out = Vec::new();
    decoder.read_to_end(&mut out).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("bz2 decompress error: {e}"))
    })?;
    Ok(PyBytes::new(py, &out))
}

#[pyfunction]
fn compress_lzma<'py>(py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    let mut out = Vec::new();
    lzma_rs::lzma_compress(&mut std::io::Cursor::new(data), &mut out).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("lzma compress error: {e}"))
    })?;
    Ok(PyBytes::new(py, &out))
}

#[pyfunction]
fn decompress_lzma<'py>(py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    let mut out = Vec::new();
    lzma_rs::lzma_decompress(&mut std::io::Cursor::new(data), &mut out).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("lzma decompress error: {e}"))
    })?;
    Ok(PyBytes::new(py, &out))
}

#[pyfunction]
fn compress_zlib<'py>(py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    use flate2::write::ZlibEncoder;

    let mut encoder = ZlibEncoder::new(Vec::new(), flate2::Compression::default());
    encoder.write_all(data).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("zlib compress error: {e}"))
    })?;
    let out = encoder.finish().map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("zlib compress finish error: {e}"))
    })?;
    Ok(PyBytes::new(py, &out))
}

#[pyfunction]
fn decompress_zlib<'py>(py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    use flate2::read::ZlibDecoder;
    use std::io::Read;

    let mut decoder = ZlibDecoder::new(data);
    let mut out = Vec::new();
    decoder.read_to_end(&mut out).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("zlib decompress error: {e}"))
    })?;
    Ok(PyBytes::new(py, &out))
}

#[pyfunction]
fn compress_zstd<'py>(py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    let out = zstd::bulk::compress(data, 0).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("zstd compress error: {e}"))
    })?;
    Ok(PyBytes::new(py, &out))
}

#[pyfunction]
fn decompress_zstd<'py>(py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    let out = zstd::bulk::decompress(data, 64 * 1024 * 1024).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("zstd decompress error: {e}"))
    })?;
    Ok(PyBytes::new(py, &out))
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "compression")?;
    m.add_class::<GzipCompressor>()?;
    m.add_class::<BrotliCompressor>()?;
    m.add_function(wrap_pyfunction!(compress_bz2, &m)?)?;
    m.add_function(wrap_pyfunction!(decompress_bz2, &m)?)?;
    m.add_function(wrap_pyfunction!(compress_lzma, &m)?)?;
    m.add_function(wrap_pyfunction!(decompress_lzma, &m)?)?;
    m.add_function(wrap_pyfunction!(compress_zlib, &m)?)?;
    m.add_function(wrap_pyfunction!(decompress_zlib, &m)?)?;
    m.add_function(wrap_pyfunction!(compress_zstd, &m)?)?;
    m.add_function(wrap_pyfunction!(decompress_zstd, &m)?)?;
    parent.add_submodule(&m)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item("flama._core.compression", &m)?;
    Ok(())
}
