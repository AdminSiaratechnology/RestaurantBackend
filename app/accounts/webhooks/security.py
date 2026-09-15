import hashlib
import hmac


def verify_uber_signature(
    payload: bytes,
    signature: str,
    client_secret: str,
) -> bool:

    if not payload:
        return False

    if not signature:
        return False

    if not client_secret:
        return False

    # -----------------------------------------------------
    # Normalize signature
    # -----------------------------------------------------

    received_signature = signature.strip()

    # Support:
    #
    # abc123...
    #
    # sha256=abc123...
    #

    if received_signature.lower().startswith("sha256="):
        received_signature = received_signature[
            len("sha256="):
        ]

    # -----------------------------------------------------
    # Generate expected signature
    # -----------------------------------------------------

    expected_signature = hmac.new(
        client_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # -----------------------------------------------------
    # Constant-time comparison
    # -----------------------------------------------------

    return hmac.compare_digest(
        expected_signature.lower(),
        received_signature.lower(),
    )