"""Message encryption for Web Push (RFC 8291) with the aes128gcm content coding (RFC 8188)."""

import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RECORD_SIZE = 4096
# One record: payload + delimiter (1) + GCM tag (16) must fit into RECORD_SIZE
MAX_PAYLOAD = RECORD_SIZE - 17


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def public_bytes(key: ec.EllipticCurvePrivateKey) -> bytes:
    """Uncompressed P-256 point (65 bytes), the form browsers and RFC 8291 use."""
    return key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def encrypt(
    payload: bytes,
    ua_public: bytes,
    auth_secret: bytes,
    *,
    ephemeral_key: ec.EllipticCurvePrivateKey | None = None,
    salt: bytes | None = None,
) -> bytes:
    """Encrypt payload for one subscription and return the request body.

    ua_public (p256dh, 65 bytes) and auth_secret (16 bytes) come from the browser's subscription.
    ephemeral_key and salt are fresh for every message; they are parameters only for the
    test vector in RFC 8291, Appendix A.
    """
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload too large ({len(payload)} > {MAX_PAYLOAD} bytes)")
    if len(auth_secret) != 16:
        raise ValueError("auth secret must be 16 bytes")
    receiver = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    ephemeral_key = ephemeral_key or ec.generate_private_key(ec.SECP256R1())
    salt = salt if salt is not None else os.urandom(16)
    as_public = public_bytes(ephemeral_key)

    ecdh_secret = ephemeral_key.exchange(ec.ECDH(), receiver)
    ikm = _hkdf(auth_secret, ecdh_secret, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)

    # \x02 marks the last (and only) record; no padding
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(as_public)]) + as_public
    return header + ciphertext
