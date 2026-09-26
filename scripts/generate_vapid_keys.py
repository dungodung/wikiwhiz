#!/usr/bin/env python3
"""Generate a VAPID keypair for Web Push, printed as envvar lines.

Usage:
  python3 scripts/generate_vapid_keys.py

Run once per deployment and store the output as VAPID_PUBLIC_KEY /
VAPID_PRIVATE_KEY (see .env.example locally, `toolforge envvars create` in
production). The keypair identifies this application server to push
services; regenerating it invalidates every existing subscription, since
browsers bind a subscription to the public key it was created with -- so
treat these as long-lived, and don't rotate them casually.

Both keys are emitted as the unpadded base64url the Web Push ecosystem
expects: the public key is what the browser passes as
applicationServerKey, and the private key is what pywebpush signs with.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> int:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    # Uncompressed point (0x04 || X || Y), 65 bytes -- the form
    # applicationServerKey must be in.
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    private_raw = private_key.private_numbers().private_value.to_bytes(32, "big")

    print("# Add these to .env (local) or `toolforge envvars create` (production).")
    print("# Keep the private key secret; it must never be served to a browser.")
    print(f"VAPID_PUBLIC_KEY={_b64(public_raw)}")
    print(f"VAPID_PRIVATE_KEY={_b64(private_raw)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
