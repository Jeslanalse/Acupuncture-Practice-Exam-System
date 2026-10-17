"""本地 HTTPS 证书：首次启动自动生成「本地 CA + 服务器证书」。

产物目录（默认 `server/certs/`，可用 `AUTH_TLS_DIR` 覆盖）：
    ca.crt / ca.key          本地 CA（客户端只信这个）
    server.crt / server.key  给 127.0.0.1 / localhost 用的服务器证书

设计上刻意不做「跳过校验」：
- 服务端只跑 HTTPS；
- 客户端把 `ca.crt` 当作信任锚做完整校验（主机名、有效期、签发链）。

证书缺失、临近过期（7 天）或与 CA 不匹配时自动补发；`python server/tls.py --force`
强制重建整条证书链。CA 仍在有效期内时只补发叶子证书，客户端信任文件无需更换。
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import os
import sys

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("需要 cryptography：python -m pip install cryptography") from exc

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.join(HERE, "certs")

RENEW_BEFORE_DAYS = 7
CA_DAYS = 3650
SERVER_DAYS = 825
COMMON_NAME = "127.0.0.1"
CA_COMMON_NAME = "Acupuncture Practice Exam Local CA"


def paths():
    directory = os.environ.get("AUTH_TLS_DIR", DEFAULT_DIR)
    return {
        "dir": directory,
        "ca": os.path.join(directory, "ca.crt"),
        "ca_key": os.path.join(directory, "ca.key"),
        "cert": os.path.join(directory, "server.crt"),
        "key": os.path.join(directory, "server.key"),
    }


def _write(path: str, data: bytes, private: bool = False) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    if private:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _pem_key(key) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _pem_cert(cert) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def _not_after(cert) -> dt.datetime:
    value = getattr(cert, "not_valid_after_utc", None)
    if value is not None:
        return value
    return cert.not_valid_after.replace(tzinfo=dt.timezone.utc)


def _usable(cert_path: str, minimum_days: int) -> bool:
    if not os.path.exists(cert_path):
        return False
    try:
        with open(cert_path, "rb") as handle:
            cert = x509.load_pem_x509_certificate(handle.read())
    except (OSError, ValueError):
        return False
    return _not_after(cert) > dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=minimum_days)


def _load_ca(ca_path: str, ca_key_path: str):
    try:
        with open(ca_path, "rb") as handle:
            ca_cert = x509.load_pem_x509_certificate(handle.read())
        with open(ca_key_path, "rb") as handle:
            ca_key = serialization.load_pem_private_key(handle.read(), password=None)
    except (OSError, ValueError):
        return None
    return ca_cert, ca_key


def _build_ca():
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = dt.datetime.now(dt.timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CA_COMMON_NAME)])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=CA_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=True,
                crl_sign=True, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    return ca_cert, ca_key


def _build_server(ca_cert, ca_key):
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = dt.datetime.now(dt.timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, COMMON_NAME)])
    san = x509.SubjectAlternativeName([
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.DNSName("localhost"),
    ])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=SERVER_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=True,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(san, critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )
    return server_cert, server_key


def _issued_by(cert_path: str, ca_cert) -> bool:
    try:
        with open(cert_path, "rb") as handle:
            cert = x509.load_pem_x509_certificate(handle.read())
    except (OSError, ValueError):
        return False
    return cert.issuer == ca_cert.subject


def ensure_certificate(force: bool = False) -> tuple[str, str]:
    """保证目录里有可用的证书链，返回 (server.crt, server.key) 路径。"""
    target = paths()
    os.makedirs(target["dir"], exist_ok=True)

    if not force and _usable(target["cert"], RENEW_BEFORE_DAYS):
        ca = _load_ca(target["ca"], target["ca_key"])
        if (
            ca is not None
            and _usable(target["ca"], RENEW_BEFORE_DAYS)
            and _issued_by(target["cert"], ca[0])
            and os.path.exists(target["key"])
        ):
            return target["cert"], target["key"]

    ca = _load_ca(target["ca"], target["ca_key"])
    if force or ca is None or not _usable(target["ca"], RENEW_BEFORE_DAYS):
        ca_cert, ca_key = _build_ca()
        _write(target["ca"], _pem_cert(ca_cert))
        _write(target["ca_key"], _pem_key(ca_key), private=True)
    else:
        ca_cert, ca_key = ca

    server_cert, server_key = _build_server(ca_cert, ca_key)
    _write(target["cert"], _pem_cert(server_cert))
    _write(target["key"], _pem_key(server_key), private=True)
    return target["cert"], target["key"]


def main() -> int:
    parser = argparse.ArgumentParser(description="生成/检查本地 HTTPS 证书")
    parser.add_argument("--force", action="store_true", help="强制重建整条证书链（含 CA）")
    args = parser.parse_args()

    cert, key = ensure_certificate(force=args.force)
    with open(cert, "rb") as handle:
        leaf = x509.load_pem_x509_certificate(handle.read())
    target = paths()
    print(f"证书链目录：{target['dir']}")
    print(f"服务器证书：{cert}")
    print(f"服务器私钥：{key}")
    print(f"客户端信任：{target['ca']}")
    print(f"生效至：{_not_after(leaf).isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
