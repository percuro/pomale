"""Web Push message encryption against RFC 8291, Appendix A, and a round trip."""

import os
import unittest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.services.webpush.crypto import MAX_PAYLOAD, encrypt, public_bytes
from app.services.webpush.encoding import b64url_decode, b64url_encode

# RFC 8291, Appendix A
PLAINTEXT = "V2hlbiBJIGdyb3cgdXAsIEkgd2FudCB0byBiZSBhIHdhdGVybWVsb24"
AS_PRIVATE = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
AS_PUBLIC = "BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8"
UA_PRIVATE = "q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94"
UA_PUBLIC = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
SALT = "DGv6ra1nlYgDCS1FRnbzlw"
AUTH_SECRET = "BTBZMqHH6r4Tts7J_aSIgg"
MESSAGE = (
    "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_"
    "yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
)


def private_key(value: str) -> ec.EllipticCurvePrivateKey:
    return ec.derive_private_key(int.from_bytes(b64url_decode(value), "big"), ec.SECP256R1())


def decrypt(body: bytes, ua_key: ec.EllipticCurvePrivateKey, auth_secret: bytes) -> bytes:
    """What the browser does (RFC 8291, section 3.4, and RFC 8188)."""
    salt, record_size, id_length = body[:16], int.from_bytes(body[16:20], "big"), body[20]
    as_public = body[21 : 21 + id_length]
    ciphertext = body[21 + id_length :]
    assert len(ciphertext) <= record_size
    ua_public = public_bytes(ua_key)
    sender = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
    secret = ua_key.exchange(ec.ECDH(), sender)

    def hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)

    ikm = hkdf(auth_secret, secret, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    padded = AESGCM(cek).decrypt(nonce, ciphertext, None)
    content = padded.rstrip(b"\x00")
    assert content.endswith(b"\x02"), "last record delimiter"
    return content[:-1]


class EncryptTest(unittest.TestCase):
    def test_rfc8291_appendix_a(self):
        sender = private_key(AS_PRIVATE)
        self.assertEqual(b64url_encode(public_bytes(sender)), AS_PUBLIC)
        self.assertEqual(b64url_encode(public_bytes(private_key(UA_PRIVATE))), UA_PUBLIC)
        body = encrypt(
            b64url_decode(PLAINTEXT),
            b64url_decode(UA_PUBLIC),
            b64url_decode(AUTH_SECRET),
            ephemeral_key=sender,
            salt=b64url_decode(SALT),
        )
        self.assertEqual(b64url_encode(body), MESSAGE)

    def test_round_trip_with_fresh_keys(self):
        receiver = ec.generate_private_key(ec.SECP256R1())
        auth_secret = os.urandom(16)
        payload = '{"title": "Lesen ✓"}'.encode()
        first = encrypt(payload, public_bytes(receiver), auth_secret)
        second = encrypt(payload, public_bytes(receiver), auth_secret)
        self.assertNotEqual(first, second)  # new salt and key every time
        self.assertEqual(decrypt(first, receiver, auth_secret), payload)
        self.assertEqual(decrypt(second, receiver, auth_secret), payload)

    def test_limits(self):
        receiver = public_bytes(ec.generate_private_key(ec.SECP256R1()))
        self.assertEqual(len(encrypt(b"x" * MAX_PAYLOAD, receiver, os.urandom(16))), 86 + 4096)
        with self.assertRaises(ValueError):
            encrypt(b"x" * (MAX_PAYLOAD + 1), receiver, os.urandom(16))
        with self.assertRaises(ValueError):
            encrypt(b"x", receiver, os.urandom(15))
        with self.assertRaises(ValueError):
            encrypt(b"x", b"\x04" + b"\x00" * 64, os.urandom(16))

    def test_b64url(self):
        self.assertEqual(b64url_decode("AQ"), b"\x01")
        self.assertEqual(b64url_decode("AQ=="), b"\x01")
        for bad in ("", "a+b", "a/b", "ä"):
            with self.assertRaises(ValueError, msg=bad):
                b64url_decode(bad)


if __name__ == "__main__":
    unittest.main()
