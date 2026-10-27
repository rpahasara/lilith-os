#!/usr/bin/env python3

import re

PATTERNS = [
    # Common API/token styles
    (re.compile(r'(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{12,}\b'),
     r'\1[REDACTED_TOKEN]'),

    (re.compile(r'(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|auth[_ -]?token|secret)\b\s*[:=]\s*[\'"]?[A-Za-z0-9._~+/=-]{8,}[\'"]?'),
     r'\1=[REDACTED_SECRET]'),

    # JWTs
    (re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b'),
     '[REDACTED_JWT]'),

    # OTP / verification / recovery / passcodes
    (re.compile(r'(?i)\b(otp|one[- ]time(?: password| code)?|verification code|security code|passcode|recovery code|login code|confirmation code)\b'
                r'(\s*(?:is|:|=|-)?\s*)([A-Z0-9]{4,12})\b'),
     r'\1\2[REDACTED_CODE]'),

    # Generic six-digit code when explicitly code-like context precedes it
    (re.compile(r'(?i)\b(code|pin)\b(\s*(?:is|:|=|-)?\s*)(\d{4,8})\b'),
     r'\1\2[REDACTED_CODE]'),

    # AWS access key IDs
    (re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
     '[REDACTED_AWS_ACCESS_KEY]'),

    # GitHub classic/fine-grained-ish token prefixes
    (re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'),
     '[REDACTED_GITHUB_TOKEN]'),

    # Google API key-like values
    (re.compile(r'\bAIza[0-9A-Za-z_-]{30,}\b'),
     '[REDACTED_GOOGLE_API_KEY]'),

    # Slack tokens
    (re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b'),
     '[REDACTED_SLACK_TOKEN]'),

    # Long suspicious hex/base64-ish secrets
    (re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*[^\s,;]{6,}'),
     r'\1=[REDACTED_PASSWORD]'),
]

# Query parameters commonly carrying sensitive material
URL_PARAM_PATTERN = re.compile(
    r'(?i)([?&](?:token|access_token|auth|signature|sig|key|code|secret|'
    r'X-Amz-Signature|X-Amz-Credential)=)([^&#\s]+)'
)


def redact_sensitive(value):
    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    text = value

    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)

    text = URL_PARAM_PATTERN.sub(r'\1[REDACTED]', text)

    return text


if __name__ == "__main__":
    import sys
    print(redact_sensitive(sys.stdin.read()))
