//! Compression and tar archiving primitives exposed to Python.
//!
//! The module is built around a single [`Encoder<W>`] type that wraps any of the supported
//! compression backends (or none) over an arbitrary [`Write`]. All public entry points —
//! [`compress`], [`decompress`], [`Compressor`], [`tar`], [`untar`] — delegate to this
//! abstraction so that adding or changing a backend only requires editing the [`Encoder`]
//! enum.

use ::tar::{Archive, Builder};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use std::fs::DirEntry;
use std::io::{BufWriter, Cursor, Read, Write};
use std::path::{Component, Path};
use std::str::FromStr;

const BUF_SIZE: usize = 4096;
const TAR_PY_BUF_SIZE: usize = 64 * 1024;

// ---------------------------------------------------------------------------
// Format and parameters
// ---------------------------------------------------------------------------

/// Supported compression backends.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Format {
    Bz2,
    Lzma,
    Zlib,
    Zstd,
    Gzip,
    Brotli,
}

impl FromStr for Format {
    type Err = PyErr;

    fn from_str(s: &str) -> PyResult<Self> {
        match s {
            "bz2" => Ok(Self::Bz2),
            "lzma" => Ok(Self::Lzma),
            "zlib" => Ok(Self::Zlib),
            "zstd" => Ok(Self::Zstd),
            "gzip" => Ok(Self::Gzip),
            "brotli" => Ok(Self::Brotli),
            _ => Err(PyValueError::new_err(format!("unknown format '{s}'"))),
        }
    }
}

/// Backend-specific compression parameters with sensible defaults.
#[derive(Clone, Copy)]
struct Params {
    gzip_level: u32,
    brotli_quality: u32,
    brotli_lgwin: u32,
    zstd_level: i32,
}

impl Default for Params {
    fn default() -> Self {
        Self {
            gzip_level: 9,
            brotli_quality: 4,
            brotli_lgwin: 22,
            zstd_level: 0,
        }
    }
}

impl Params {
    /// Build [`Params`] from a Python ``dict`` of overrides; absent keys keep defaults.
    fn from_dict(d: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        let mut p = Self::default();
        let Some(d) = d else { return Ok(p) };
        if let Some(v) = d.get_item("level")? {
            p.gzip_level = v.extract()?;
        }
        if let Some(v) = d.get_item("quality")? {
            p.brotli_quality = v.extract()?;
        }
        if let Some(v) = d.get_item("lgwin")? {
            p.brotli_lgwin = v.extract()?;
        }
        Ok(p)
    }
}

/// Build an [`std::io::Error`]-to-[`PyErr`] converter that prefixes errors with *context*.
fn map_io(context: &'static str) -> impl Fn(std::io::Error) -> PyErr {
    move |e| PyRuntimeError::new_err(format!("{context}: {e}"))
}

// ---------------------------------------------------------------------------
// PyWriter — std::io::Write adapter for a Python file-like object
// ---------------------------------------------------------------------------

/// Adapter implementing [`Write`] on top of a Python file-like object.
///
/// Each [`Write::write`] re-acquires the GIL and invokes ``inner.write(bytes)``; callers should
/// wrap [`PyWriter`] in a [`BufWriter`] to amortise the cost across many small writes.
struct PyWriter {
    inner: Py<PyAny>,
    written: usize,
}

impl PyWriter {
    const fn new(inner: Py<PyAny>) -> Self {
        Self { inner, written: 0 }
    }
}

impl Write for PyWriter {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        Python::attach(|py| {
            self.inner
                .call_method1(py, "write", (PyBytes::new(py, buf),))
                .map_err(|e: PyErr| std::io::Error::other(e.to_string()))?;
            self.written += buf.len();
            Ok(buf.len())
        })
    }

    fn flush(&mut self) -> std::io::Result<()> {
        Python::attach(|py| {
            // BytesIO.flush is a no-op; ignore failures from non-flushable streams.
            let _ = self.inner.call_method0(py, "flush");
            Ok(())
        })
    }
}

// ---------------------------------------------------------------------------
// LzmaWriter — buffer-and-finish adapter (lzma-rs lacks a streaming encoder)
// ---------------------------------------------------------------------------

/// Buffer-and-finish [`Write`] adapter that emits an LZMA stream on [`LzmaWriter::finish`].
///
/// `lzma-rs` lacks a streaming encoder so input is collected in memory and compressed in a
/// single shot when the writer is finalised.
struct LzmaWriter<W: Write> {
    inner: W,
    buffer: Vec<u8>,
}

impl<W: Write> LzmaWriter<W> {
    const fn new(inner: W) -> Self {
        Self {
            inner,
            buffer: Vec::new(),
        }
    }

    fn finish(mut self) -> std::io::Result<W> {
        lzma_rs::lzma_compress(&mut Cursor::new(&self.buffer), &mut self.inner)
            .map_err(|e| std::io::Error::other(format!("lzma compress: {e}")))?;
        Ok(self.inner)
    }

    const fn get_mut(&mut self) -> &mut W {
        &mut self.inner
    }
}

impl<W: Write> Write for LzmaWriter<W> {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        self.buffer.extend_from_slice(buf);
        Ok(buf.len())
    }

    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Encoder — Write wrapper that selects a backend per Format
// ---------------------------------------------------------------------------

/// [`Write`] wrapper that dispatches to the streaming encoder of a chosen [`Format`].
enum Encoder<W: Write> {
    Plain(W),
    Gzip(flate2::write::GzEncoder<W>),
    Zlib(flate2::write::ZlibEncoder<W>),
    Bz2(bzip2::write::BzEncoder<W>),
    Zstd(zstd::Encoder<'static, W>),
    // Boxed because brotli's encoder state is several KB; keeps the enum small.
    Brotli(Box<brotli::CompressorWriter<W>>),
    Lzma(LzmaWriter<W>),
}

impl<W: Write> Encoder<W> {
    fn new(format: Option<Format>, writer: W, params: Params) -> std::io::Result<Self> {
        Ok(match format {
            None => Self::Plain(writer),
            Some(Format::Gzip) => Self::Gzip(flate2::write::GzEncoder::new(
                writer,
                flate2::Compression::new(params.gzip_level),
            )),
            Some(Format::Zlib) => Self::Zlib(flate2::write::ZlibEncoder::new(writer, flate2::Compression::default())),
            Some(Format::Bz2) => Self::Bz2(bzip2::write::BzEncoder::new(writer, bzip2::Compression::best())),
            Some(Format::Zstd) => Self::Zstd(zstd::Encoder::new(writer, params.zstd_level)?),
            Some(Format::Brotli) => Self::Brotli(Box::new(brotli::CompressorWriter::new(
                writer,
                BUF_SIZE,
                params.brotli_quality,
                params.brotli_lgwin,
            ))),
            Some(Format::Lzma) => Self::Lzma(LzmaWriter::new(writer)),
        })
    }

    fn finish(self) -> std::io::Result<W> {
        match self {
            Self::Plain(w) => Ok(w),
            Self::Gzip(e) => e.finish(),
            Self::Zlib(e) => e.finish(),
            Self::Bz2(e) => e.finish(),
            Self::Zstd(e) => e.finish(),
            Self::Brotli(e) => Ok((*e).into_inner()),
            Self::Lzma(e) => e.finish(),
        }
    }

    fn get_mut(&mut self) -> &mut W {
        match self {
            Self::Plain(w) => w,
            Self::Gzip(e) => e.get_mut(),
            Self::Zlib(e) => e.get_mut(),
            Self::Bz2(e) => e.get_mut(),
            Self::Zstd(e) => e.get_mut(),
            Self::Brotli(e) => e.get_mut(),
            Self::Lzma(e) => e.get_mut(),
        }
    }
}

impl<W: Write> Write for Encoder<W> {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        match self {
            Self::Plain(w) => w.write(buf),
            Self::Gzip(e) => e.write(buf),
            Self::Zlib(e) => e.write(buf),
            Self::Bz2(e) => e.write(buf),
            Self::Zstd(e) => e.write(buf),
            Self::Brotli(e) => e.write(buf),
            Self::Lzma(e) => e.write(buf),
        }
    }

    fn flush(&mut self) -> std::io::Result<()> {
        match self {
            Self::Plain(w) => w.flush(),
            Self::Gzip(e) => e.flush(),
            Self::Zlib(e) => e.flush(),
            Self::Bz2(e) => e.flush(),
            Self::Zstd(e) => e.flush(),
            Self::Brotli(e) => e.flush(),
            Self::Lzma(e) => e.flush(),
        }
    }
}

impl Encoder<Vec<u8>> {
    /// Flush pending output and return the bytes accumulated so far, leaving the inner buffer
    /// empty so the encoder can keep producing more.
    fn drain(&mut self) -> std::io::Result<Vec<u8>> {
        self.flush()?;
        Ok(std::mem::take(self.get_mut()))
    }
}

// ---------------------------------------------------------------------------
// Decoder — one-shot decompress to a buffer
// ---------------------------------------------------------------------------

fn decompress_into(data: &[u8], format: Format) -> std::io::Result<Vec<u8>> {
    let mut out = Vec::new();
    match format {
        Format::Bz2 => {
            bzip2::read::BzDecoder::new(data).read_to_end(&mut out)?;
        }
        Format::Lzma => {
            lzma_rs::lzma_decompress(&mut Cursor::new(data), &mut out)
                .map_err(|e| std::io::Error::other(format!("lzma decompress: {e}")))?;
        }
        Format::Zlib => {
            flate2::read::ZlibDecoder::new(data).read_to_end(&mut out)?;
        }
        Format::Zstd => {
            zstd::Decoder::new(data)?.read_to_end(&mut out)?;
        }
        Format::Gzip => {
            flate2::read::GzDecoder::new(data).read_to_end(&mut out)?;
        }
        Format::Brotli => {
            brotli::Decompressor::new(data, BUF_SIZE).read_to_end(&mut out)?;
        }
    }
    Ok(out)
}

// ---------------------------------------------------------------------------
// One-shot compress / decompress
// ---------------------------------------------------------------------------

/// Compress *data* using *format*.
///
/// :param data: Raw bytes to compress.
/// :param format: One of ``"bz2"``, ``"lzma"``, ``"zlib"``, ``"zstd"``, ``"gzip"``,
///     or ``"brotli"``.
/// :param params: Format-specific options (``level`` for gzip; ``quality``/``lgwin``
///     for brotli).
/// :return: Compressed bytes.
#[pyfunction]
#[pyo3(signature = (data, format, **params))]
fn compress<'py>(
    py: Python<'py>,
    data: &[u8],
    format: &str,
    params: Option<&Bound<'py, PyDict>>,
) -> PyResult<Bound<'py, PyBytes>> {
    let fmt = Format::from_str(format)?;
    let p = Params::from_dict(params)?;
    let mut encoder = Encoder::new(Some(fmt), Vec::new(), p).map_err(map_io("compress init"))?;
    encoder.write_all(data).map_err(map_io("compress"))?;
    let out = encoder.finish().map_err(map_io("compress finish"))?;
    Ok(PyBytes::new(py, &out))
}

/// Decompress *data* using *format*.
#[pyfunction]
fn decompress<'py>(py: Python<'py>, data: &[u8], format: &str) -> PyResult<Bound<'py, PyBytes>> {
    let fmt = Format::from_str(format)?;
    let out = decompress_into(data, fmt).map_err(map_io("decompress"))?;
    Ok(PyBytes::new(py, &out))
}

// ---------------------------------------------------------------------------
// Streaming Compressor
// ---------------------------------------------------------------------------

/// Stateful chunk-by-chunk compressor.
///
/// gzip/zlib/bz2/zstd/brotli emit compressed bytes incrementally between calls;
/// lzma buffers all input until ``finish=True`` because its backing crate lacks a
/// streaming encoder.
#[pyclass]
pub struct Compressor {
    encoder: Option<Encoder<Vec<u8>>>,
}

#[pymethods]
impl Compressor {
    /// Build a stateful :class:`Compressor` for *format*.
    #[new]
    #[pyo3(signature = (format, **params))]
    fn new(format: &str, params: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        let fmt = Format::from_str(format)?;
        let p = Params::from_dict(params)?;
        let encoder = Encoder::new(Some(fmt), Vec::new(), p).map_err(map_io("compressor init"))?;
        Ok(Self { encoder: Some(encoder) })
    }

    /// Encode a chunk of raw bytes and return the compressed output produced so far.
    ///
    /// When *finish* is true the underlying stream is finalised; further calls raise
    /// :class:`RuntimeError`.
    fn compress<'py>(&mut self, py: Python<'py>, data: &[u8], finish: bool) -> PyResult<Bound<'py, PyBytes>> {
        let out = if finish {
            let mut enc = self
                .encoder
                .take()
                .ok_or_else(|| PyRuntimeError::new_err("compressor already finished"))?;
            enc.write_all(data).map_err(map_io("compress"))?;
            enc.finish().map_err(map_io("compress finish"))?
        } else {
            let enc = self
                .encoder
                .as_mut()
                .ok_or_else(|| PyRuntimeError::new_err("compressor already finished"))?;
            enc.write_all(data).map_err(map_io("compress"))?;
            enc.drain().map_err(map_io("compress drain"))?
        };
        Ok(PyBytes::new(py, &out))
    }
}

// ---------------------------------------------------------------------------
// Tar / untar
// ---------------------------------------------------------------------------

/// Recursively append *abs* (mounted at *rel*) to *builder*, skipping dotfiles.
fn tar_walk<W: Write>(builder: &mut Builder<W>, abs: &Path, rel: &Path) -> std::io::Result<()> {
    let mut entries: Vec<_> = std::fs::read_dir(abs)?.collect::<std::io::Result<Vec<_>>>()?;
    entries.sort_by_key(DirEntry::file_name);

    for entry in entries {
        let name = entry.file_name();
        if name.to_string_lossy().starts_with('.') {
            continue;
        }
        let abs_path = entry.path();
        let rel_path = rel.join(&name);

        if entry.metadata()?.is_dir() {
            builder.append_dir(&rel_path, &abs_path)?;
            tar_walk(builder, &abs_path, &rel_path)?;
        } else {
            builder.append_path_with_name(&abs_path, &rel_path)?;
        }
    }
    Ok(())
}

/// Pack *directory* into a tar archive and stream-write it through *writer*.
///
/// When *format* is ``None`` the tar is written raw; otherwise it is piped through
/// the matching streaming encoder. Symlinks are followed and entries whose final
/// path component starts with ``"."`` are skipped, mirroring ``tarfile.add`` with
/// a dotfile filter.
///
/// The Python writer is wrapped in a [`BufWriter`] so that the GIL is acquired once per
/// flushed buffer instead of once per archive frame.
#[pyfunction]
#[pyo3(signature = (directory, writer, format=None))]
fn tar(directory: &str, writer: Py<PyAny>, format: Option<&str>) -> PyResult<usize> {
    let src = Path::new(directory);
    let fmt = format.map(Format::from_str).transpose()?;
    let buffered = BufWriter::with_capacity(TAR_PY_BUF_SIZE, PyWriter::new(writer));
    let encoder = Encoder::new(fmt, buffered, Params::default()).map_err(map_io("tar init"))?;

    let mut builder = Builder::new(encoder);
    builder.follow_symlinks(true);
    builder.append_dir(".", src).map_err(map_io("tar"))?;
    tar_walk(&mut builder, src, Path::new(".")).map_err(map_io("tar"))?;

    let encoder = builder.into_inner().map_err(map_io("tar finish"))?;
    let buffered = encoder.finish().map_err(map_io("tar finish"))?;
    let py_writer = buffered
        .into_inner()
        .map_err(|e| PyRuntimeError::new_err(format!("tar flush: {}", e.error())))?;
    Ok(py_writer.written)
}

/// Extract a tar archive from *data* into *directory*.
///
/// When *format* is ``None`` *data* is treated as raw tar; otherwise it is first
/// decompressed using the matching decoder. Entries with absolute paths or ``..``
/// components are skipped, mirroring ``tarfile``'s ``filter="data"``.
#[pyfunction]
#[pyo3(signature = (data, directory, format=None))]
fn untar(data: &[u8], directory: &str, format: Option<&str>) -> PyResult<()> {
    let dir = Path::new(directory);
    std::fs::create_dir_all(dir).map_err(map_io("untar mkdir"))?;

    let fmt = format.map(Format::from_str).transpose()?;
    let buffer: Vec<u8>;
    let bytes: &[u8] = match fmt {
        None => data,
        Some(f) => {
            buffer = decompress_into(data, f).map_err(map_io("untar decompress"))?;
            &buffer
        }
    };

    let mut archive = Archive::new(Cursor::new(bytes));
    archive.set_overwrite(true);

    for entry in archive.entries().map_err(map_io("untar entries"))? {
        let mut entry = entry.map_err(map_io("untar entry"))?;
        let path = entry.path().map_err(map_io("untar path"))?.into_owned();
        if path.is_absolute() || path.components().any(|c| matches!(c, Component::ParentDir)) {
            continue;
        }
        entry.unpack(dir.join(&path)).map_err(map_io("untar unpack"))?;
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

pub fn build(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Compressor>()?;
    m.add_function(wrap_pyfunction!(compress, m)?)?;
    m.add_function(wrap_pyfunction!(decompress, m)?)?;
    m.add_function(wrap_pyfunction!(self::tar, m)?)?;
    m.add_function(wrap_pyfunction!(self::untar, m)?)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// Round-trip *data* through an [`Encoder`]/[`decompress_into`] pair for *format*.
    fn roundtrip(format: Format, data: &[u8]) {
        let mut encoder = Encoder::new(Some(format), Vec::new(), Params::default()).unwrap();
        encoder.write_all(data).unwrap();
        let compressed = encoder.finish().unwrap();
        let decompressed = decompress_into(&compressed, format).unwrap();
        assert_eq!(decompressed, data, "{format:?} round-trip mismatch");
    }

    #[test]
    fn format_from_str_known_formats() {
        assert_eq!(Format::from_str("bz2").unwrap(), Format::Bz2);
        assert_eq!(Format::from_str("lzma").unwrap(), Format::Lzma);
        assert_eq!(Format::from_str("zlib").unwrap(), Format::Zlib);
        assert_eq!(Format::from_str("zstd").unwrap(), Format::Zstd);
        assert_eq!(Format::from_str("gzip").unwrap(), Format::Gzip);
        assert_eq!(Format::from_str("brotli").unwrap(), Format::Brotli);
    }

    #[test]
    fn format_from_str_rejects_unknown() {
        Format::from_str("snappy").expect_err("unknown format must error");
        Format::from_str("").expect_err("empty format must error");
    }

    #[test]
    fn roundtrip_all_formats() {
        let payload = b"the quick brown fox jumps over the lazy dog. \
                        the quick brown fox jumps over the lazy dog. \
                        the quick brown fox jumps over the lazy dog.";
        for fmt in [
            Format::Bz2,
            Format::Lzma,
            Format::Zlib,
            Format::Zstd,
            Format::Gzip,
            Format::Brotli,
        ] {
            roundtrip(fmt, payload);
        }
    }

    #[test]
    fn streaming_drain_yields_all_bytes() {
        let payload = b"hello world".repeat(64);
        let mut encoder = Encoder::new(Some(Format::Gzip), Vec::new(), Params::default()).unwrap();
        encoder.write_all(&payload).unwrap();
        let mid = encoder.drain().unwrap();
        let tail = encoder.finish().unwrap();
        let mut combined = mid;
        combined.extend(tail);
        let decompressed = decompress_into(&combined, Format::Gzip).unwrap();
        assert_eq!(decompressed, payload);
    }
}
