//! Signing primitives for JSON Web Signatures.
//!
//! Thin `PyO3` bindings exposing [`AsymmetricSigner`], which signs with the private half of a
//! keypair and verifies with the public one. Signers are named by their JWA registry name
//! (``EdDSA``).
//!
//! Verification goes through [`VerifyingKey::verify_strict`], so beyond the curve equation it
//! rejects small-order keys and non-canonical scalars, leaving a signature exactly one valid
//! encoding under exactly one key.

use std::str::FromStr;

use ed25519_dalek::{Signature, Signer as _, SigningKey, VerifyingKey};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rand_core::OsRng;

/// Length of an Ed25519 key, private or public, in bytes.
const KEY_LENGTH: usize = 32;

/// Length of an Ed25519 signature, in bytes.
const SIGNATURE_LENGTH: usize = 64;

/// Supported signature algorithms.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum AsymmetricAlgorithm {
    EdDsa,
}

impl FromStr for AsymmetricAlgorithm {
    type Err = PyErr;

    fn from_str(s: &str) -> PyResult<Self> {
        match s {
            "EdDSA" => Ok(Self::EdDsa),
            _ => Err(PyValueError::new_err(format!("unknown asymmetric algorithm '{s}'"))),
        }
    }
}

/// Read an Ed25519 signing key out of the caller's bytes.
///
/// A private key is exactly 32 bytes; anything else is refused.
fn signing_key(key: &[u8]) -> PyResult<SigningKey> {
    let key: [u8; KEY_LENGTH] = key
        .try_into()
        .map_err(|_| PyValueError::new_err(format!("Ed25519 private key must be {KEY_LENGTH} bytes")))?;

    Ok(SigningKey::from_bytes(&key))
}

/// Verify an Ed25519 signature.
fn ed25519_verify(message: &[u8], signature: &[u8], key: &[u8]) -> bool {
    let Ok(signature) = <[u8; SIGNATURE_LENGTH]>::try_from(signature) else {
        return false;
    };

    let Ok(key) = <[u8; KEY_LENGTH]>::try_from(key) else {
        return false;
    };

    VerifyingKey::from_bytes(&key)
        .is_ok_and(|key| key.verify_strict(message, &Signature::from_bytes(&signature)).is_ok())
}

/// `EdDSA`, where a signature is made with a private key and checked against the public one.
#[pyclass(frozen)]
pub struct AsymmetricSigner {
    algorithm: AsymmetricAlgorithm,
}

#[pymethods]
impl AsymmetricSigner {
    /// Build a signer for *algorithm*, by its JWA name.
    #[new]
    fn new(algorithm: &str) -> PyResult<Self> {
        Ok(Self {
            algorithm: AsymmetricAlgorithm::from_str(algorithm)?,
        })
    }

    /// Sign a message.
    ///
    /// The signature follows from the message and the key alone, so signing the same message twice
    /// gives the same signature.
    fn sign(&self, message: &[u8], key: &[u8]) -> PyResult<Vec<u8>> {
        match self.algorithm {
            AsymmetricAlgorithm::EdDsa => Ok(signing_key(key)?.sign(message).to_bytes().to_vec()),
        }
    }

    /// Verify a message's signature, returning false for malformed signatures and keys too.
    fn verify(&self, message: &[u8], signature: &[u8], key: &[u8]) -> bool {
        match self.algorithm {
            AsymmetricAlgorithm::EdDsa => ed25519_verify(message, signature, key),
        }
    }

    /// Generate a keypair to sign with, drawing from the operating system's randomness.
    fn generate(&self) -> (Vec<u8>, Vec<u8>) {
        match self.algorithm {
            AsymmetricAlgorithm::EdDsa => {
                let key = SigningKey::generate(&mut OsRng);

                (key.to_bytes().to_vec(), key.verifying_key().to_bytes().to_vec())
            }
        }
    }

    /// Derive the public key a private key verifies against.
    fn public_key(&self, key: &[u8]) -> PyResult<Vec<u8>> {
        match self.algorithm {
            AsymmetricAlgorithm::EdDsa => Ok(signing_key(key)?.verifying_key().to_bytes().to_vec()),
        }
    }
}

pub fn build(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AsymmetricSigner>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Decode a hex string into bytes.
    fn hex(value: &str) -> Vec<u8> {
        (0..value.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&value[i..i + 2], 16).expect("vectors are valid hex"))
            .collect()
    }

    fn eddsa() -> AsymmetricSigner {
        AsymmetricSigner::new("EdDSA").unwrap()
    }

    /// The private key of the first vector in RFC 8032, section 7.1.
    fn ed25519_key() -> Vec<u8> {
        hex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    }

    #[test]
    fn algorithms_are_named_as_jwa_names_them() {
        assert_eq!(
            AsymmetricAlgorithm::from_str("EdDSA").unwrap(),
            AsymmetricAlgorithm::EdDsa
        );
    }

    #[test]
    fn unknown_algorithms_are_refused() {
        assert!(AsymmetricAlgorithm::from_str("ES256").is_err());
        assert!(AsymmetricAlgorithm::from_str("HS256").is_err());
        assert!(AsymmetricAlgorithm::from_str("").is_err());
    }

    /// The first vector published in RFC 8032, section 7.1.
    #[test]
    fn rfc_8032_first_vector() {
        let key = ed25519_key();
        let public = hex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a");
        let signature = hex(
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46b\
             d25bf5f0595bbe24655141438e7a100b",
        );

        assert_eq!(eddsa().public_key(&key).unwrap(), public);
        assert_eq!(eddsa().sign(b"", &key).unwrap(), signature);
        assert!(eddsa().verify(b"", &signature, &public));
    }

    #[test]
    fn signs_deterministically() {
        let key = ed25519_key();

        assert_eq!(
            eddsa().sign(b"hello", &key).unwrap(),
            eddsa().sign(b"hello", &key).unwrap()
        );
    }

    #[test]
    fn generates_usable_keypairs() {
        let (key, public) = eddsa().generate();

        assert_eq!(key.len(), KEY_LENGTH);
        assert_eq!(public.len(), KEY_LENGTH);
        assert_eq!(eddsa().public_key(&key).unwrap(), public);
        assert_ne!(eddsa().generate().0, key);
        assert!(eddsa().verify(b"hello", &eddsa().sign(b"hello", &key).unwrap(), &public));
    }

    #[test]
    fn refuses_keys_that_are_not_32_bytes() {
        assert!(eddsa().sign(b"hello", &[0; 31]).is_err());
        assert!(eddsa().sign(b"hello", &[0; 33]).is_err());
        assert!(eddsa().public_key(&[0; 31]).is_err());
    }

    #[test]
    fn rejects_tampering_and_wrong_key() {
        let key = ed25519_key();
        let public = eddsa().public_key(&key).unwrap();
        let signature = eddsa().sign(b"hello", &key).unwrap();

        assert!(!eddsa().verify(b"tampered", &signature, &public));
        assert!(!eddsa().verify(b"hello", &signature, &eddsa().public_key(&[7; 32]).unwrap()));
        assert!(!eddsa().verify(b"hello", &signature, &key));
    }

    #[test]
    fn rejects_malformed_signatures_and_keys() {
        let key = ed25519_key();
        let public = eddsa().public_key(&key).unwrap();
        let signature = eddsa().sign(b"hello", &key).unwrap();

        assert!(!eddsa().verify(b"hello", &[], &public));
        assert!(!eddsa().verify(b"hello", &[0; 63], &public));
        assert!(!eddsa().verify(b"hello", &[0; 64], &public));
        assert!(!eddsa().verify(b"hello", &signature, &[0; 31]));
        // A y at or above the field prime, which is no encoding of a point.
        assert!(!eddsa().verify(b"hello", &signature, &[0xff; 32]));
    }

    #[test]
    fn rejects_small_order_keys() {
        let signature = eddsa().sign(b"hello", &ed25519_key()).unwrap();

        // The identity is a point, but never one a signature was made under.
        let mut identity = [0; KEY_LENGTH];
        identity[0] = 1;

        assert!(!eddsa().verify(b"hello", &signature, &identity));
    }

    #[test]
    fn rejects_unreduced_scalar() {
        let key = ed25519_key();
        let public = eddsa().public_key(&key).unwrap();
        let mut signature = eddsa().sign(b"hello", &key).unwrap();

        // The group order itself, which would let one signature be written more than one way.
        signature[32..].copy_from_slice(&hex("edd3f55c1a631258d69cf7a2def9de1400000000000000000000000000000010"));

        assert!(!eddsa().verify(b"hello", &signature, &public));
    }
}
