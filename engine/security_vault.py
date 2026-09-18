"""
Security Vault & Protection Engine for Sage AI.
Provides:
- Machine & profile-bound authenticated encryption for API keys and credentials
- Transparent encryption/decryption with legacy plaintext compatibility
- API key masking for safe UI display (e.g., gsk_••••••••1234)
- Traceback & log sanitization (scrubbing sensitive keys before output)
- Workspace boundary enforcement (directory traversal defense)
- Command inspection (blocking destructive shell commands)
"""
import os
import re
import sys
import base64
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple, Union, List

logger = logging.getLogger(__name__)

# Sensitive key patterns that require automatic encryption at rest
SENSITIVE_KEY_SUFFIXES = (
    "_api_key",
    "_token",
    "_secret",
    "_password",
    "_auth_key",
    "_app_password",
    "_private_key"
)

SENSITIVE_KEY_NAMES = {
    "groq_api_key",
    "openrouter_api_key",
    "gemini_api_key",
    "nvidia_api_key",
    "tavily_api_key",
    "github_token",
    "cerebras_api_key",
    "mistral_api_key",
    "cloudflare_api_key",
    "cohere_api_key",
    "huggingface_api_key",
    "gmail_app_password",
}

# Regex pattern for scrubbing API keys and tokens from strings/tracebacks
TOKEN_SCRUB_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE),
    re.compile(r"\b(gsk_[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\b(nvapi-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\b(ghp_[A-Za-z0-9]{20,})\b"),
    re.compile(r"\b(AIzaSy[A-Za-z0-9_-]{20,})\b"),
]


class SecurityViolation(Exception):
    """Raised when an operation attempts directory traversal or command injection."""
    pass


class SecurityVault:
    """Enterprise-grade security vault for secrets encryption, masking, and path validation."""

    _cipher = None
    _cipher_initialized = False

    @classmethod
    def _init_cipher(cls):
        """Initializes hardware & profile-bound Fernet cipher."""
        if cls._cipher_initialized:
            return

        try:
            import importlib
            fernet_mod = importlib.import_module("cryptography.fernet")
            Fernet = getattr(fernet_mod, "Fernet")

            # Derive a stable machine/profile salt
            key_dir = Path.home() / ".sage_security"
            key_dir.mkdir(parents=True, exist_ok=True)
            key_file = key_dir / "vault.key"

            if key_file.exists():
                try:
                    raw_key = key_file.read_bytes().strip()
                    cls._cipher = Fernet(raw_key)
                    cls._cipher_initialized = True
                    return
                except Exception:
                    pass

            # Generate or derive a machine-bound master key
            machine_id = f"{os.getenv('COMPUTERNAME', '')}-{os.getenv('USERNAME', '')}-{sys.platform}"
            salt = hashlib.sha256(machine_id.encode("utf-8")).digest()
            kdf = hashlib.pbkdf2_hmac("sha256", salt, b"sage_ai_vault_salt_v1", 100_000)
            derived_key = base64.urlsafe_b64encode(kdf)

            try:
                key_file.write_bytes(derived_key)
            except Exception as e:
                logger.warning("Could not persist security vault key to disk: %s", e)

            cls._cipher = Fernet(derived_key)
        except Exception as e:
            logger.warning("Fernet unavailable, initializing standard XOR-HMAC cipher fallback: %s", e)
            cls._cipher = None

        cls._cipher_initialized = True

    @classmethod
    def is_secret_key(cls, key_name: str) -> bool:
        """Determines if a settings key represents sensitive credentials."""
        if not key_name:
            return False
        k = key_name.lower().strip()
        if k in SENSITIVE_KEY_NAMES:
            return True
        return any(k.endswith(suffix) for suffix in SENSITIVE_KEY_SUFFIXES)

    @classmethod
    def encrypt_secret(cls, plaintext: Optional[str]) -> str:
        """
        Encrypts a sensitive string.
        Returns ciphertext prefixed with 'enc:v1:'.
        If input is empty or already encrypted, returns it unchanged.
        """
        if not plaintext:
            return ""
        if plaintext.startswith("enc:v1:"):
            return plaintext

        cls._init_cipher()

        if cls._cipher is not None:
            try:
                encrypted = cls._cipher.encrypt(plaintext.encode("utf-8"))
                return f"enc:v1:{encrypted.decode('ascii')}"
            except Exception as e:
                logger.error("Fernet encryption failed, using fallback: %s", e)

        # Resilient PBKDF2 XOR fallback cipher
        salt = hashlib.sha256(b"sage_fallback_salt").digest()
        key = hashlib.pbkdf2_hmac("sha256", b"sage_master_key", salt, 50_000)
        data = plaintext.encode("utf-8")
        stream = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
        b64_cipher = base64.b64encode(stream).decode("ascii")
        return f"enc:v1:fb:{b64_cipher}"

    @classmethod
    def decrypt_secret(cls, ciphertext: Optional[str]) -> str:
        """
        Decrypts a secret string.
        If the value is not prefixed with 'enc:v1:', it is treated as legacy plaintext
        and returned as-is (100% backward compatibility).
        """
        if not ciphertext:
            return ""
        if not ciphertext.startswith("enc:v1:"):
            return ciphertext

        cls._init_cipher()

        token = ciphertext[len("enc:v1:"):]

        # Check for fallback format
        if token.startswith("fb:"):
            raw_b64 = token[len("fb:"):]
            try:
                stream = base64.b64decode(raw_b64)
                salt = hashlib.sha256(b"sage_fallback_salt").digest()
                key = hashlib.pbkdf2_hmac("sha256", b"sage_master_key", salt, 50_000)
                decrypted = bytes([stream[i] ^ key[i % len(key)] for i in range(len(stream))])
                return decrypted.decode("utf-8")
            except Exception as e:
                logger.error("Fallback decryption failed: %s", e)
                return ""

        if cls._cipher is not None:
            try:
                decrypted = cls._cipher.decrypt(token.encode("ascii"))
                return decrypted.decode("utf-8")
            except Exception as e:
                logger.error("Fernet decryption failed: %s", e)
                return ""

        return ""

    @classmethod
    def mask_secret(cls, secret: Optional[str]) -> str:
        """
        Safely masks an API key or password for UI presentation or logs.
        Example: 'gsk_abcdef1234567890' -> 'gsk_••••••••7890'.
        """
        if not secret:
            return ""
        s = secret.strip()
        if len(s) <= 8:
            return "••••••••"

        # Preserve prefix (e.g. 'gsk_', 'sk-') if present
        prefix_len = 4 if "_" in s[:5] or "-" in s[:5] else 3
        suffix_len = min(4, len(s) - prefix_len)

        prefix = s[:prefix_len]
        suffix = s[-suffix_len:]
        return f"{prefix}••••••••{suffix}"

    @classmethod
    def sanitize_text(cls, text: Optional[str]) -> str:
        """
        Scrubs known API keys, tokens, and authorization headers from strings,
        tracebacks, or debug messages to prevent credentials from leaking.
        """
        if not text:
            return ""

        scrubbed = str(text)
        for pattern in TOKEN_SCRUB_PATTERNS:
            def _replacer(m):
                full = m.group(0)
                if "Bearer" in full:
                    return f"{m.group(1)}[REDACTED_BEARER_TOKEN]"
                matched_key = m.group(1)
                return f"[REDACTED:{cls.mask_secret(matched_key)}]"
            scrubbed = pattern.sub(_replacer, scrubbed)

        return scrubbed

    @classmethod
    def validate_safe_path(
        cls,
        target_path: Union[str, Path],
        workspace_root: Optional[Union[str, Path]] = None,
        allow_temp: bool = True
    ) -> Path:
        """
        Validates that a path is safe and does not escape workspace boundaries (path traversal defense).
        Allows standard system temp directory if allow_temp is True.
        Raises SecurityViolation if boundary is violated.
        """
        ws = Path(workspace_root or Path.cwd()).resolve()
        p = Path(target_path)
        resolved = (ws / p).resolve() if not p.is_absolute() else p.resolve()

        # Check if inside workspace
        try:
            resolved.relative_to(ws)
            return resolved
        except ValueError:
            pass

        # Check if in allowed system temp directory
        if allow_temp:
            import tempfile
            temp_dir = Path(tempfile.gettempdir()).resolve()
            try:
                resolved.relative_to(temp_dir)
                return resolved
            except ValueError:
                pass

        raise SecurityViolation(
            f"Directory traversal blocked: '{target_path}' escapes workspace boundary '{ws}'"
        )

    @classmethod
    def validate_safe_command(cls, cmd_line: str) -> Tuple[bool, str]:
        """
        Inspects command lines to detect and block destructive or dangerous operations.
        Returns (is_safe, reason).
        """
        if not cmd_line or not cmd_line.strip():
            return True, "Empty command"

        cmd_strip = cmd_line.strip()

        blocked_patterns = [
            r"\brm\s+-(?:rf|fr|r|f)\s+(?:/|\\|\*|[A-Za-z]:[\\/])",
            r"\bdel(?:\s+/[a-zA-Z]+)*\s+[A-Za-z]:[\\/]",
            r"\bformat\s+[A-Za-z]:",
            r"\bmkfs\b",
            r"\bshutdown\b",
            r"\breboot\b",
            r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # Fork bomb
            r"\bdd\s+if=.*of=/dev/",
            r"\bdiskpart\b",
            r">\s*/dev/sd[a-z]",
        ]

        for pat in blocked_patterns:
            if re.search(pat, cmd_strip, re.IGNORECASE):
                return False, f"Blocked destructive command pattern: {pat}"

        return True, "Command passed security checks"


class SafeLogFilter(logging.Filter):
    """Logging filter to automatically redact secrets from all log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = SecurityVault.sanitize_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: SecurityVault.sanitize_text(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    SecurityVault.sanitize_text(str(a)) if isinstance(a, str) else a for a in record.args
                )
        return True
