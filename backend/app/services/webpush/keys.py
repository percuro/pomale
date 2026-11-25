"""The instance's VAPID key pair: created on first start, then kept in instance_secrets."""

import logging
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InstanceSecret
from app.services.webpush.crypto import public_bytes
from app.services.webpush.encoding import b64url_encode

VAPID_SECRET_NAME = "vapid_private_key"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VapidKeys:
    private_key: ec.EllipticCurvePrivateKey
    # base64url of the uncompressed point: the browser's applicationServerKey and the "k" in the header
    public_key: str
    private_pem: str


def _from_pem(pem: str) -> VapidKeys:
    key = serialization.load_pem_private_key(pem.encode("ascii"), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("stored VAPID key is not a P-256 key")
    return VapidKeys(private_key=key, public_key=b64url_encode(public_bytes(key)), private_pem=pem)


def load_vapid_keys(db: Session) -> VapidKeys | None:
    secret = db.get(InstanceSecret, VAPID_SECRET_NAME)
    return _from_pem(secret.value) if secret else None


def ensure_vapid_keys(db: Session) -> VapidKeys:
    """Return the key pair, creating it once. Safe if two processes race: the first insert wins."""
    keys = load_vapid_keys(db)
    if keys is not None:
        return keys
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode("ascii")
    db.add(InstanceSecret(name=VAPID_SECRET_NAME, value=pem))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        logger.info("VAPID key created; it is stored in the database, keep backups of it")
    keys = load_vapid_keys(db)
    assert keys is not None
    return keys
