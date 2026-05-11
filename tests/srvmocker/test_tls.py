import ipaddress
import ssl
from pathlib import Path

import pytest
from aiohttp import ClientSession, TCPConnector

from asyncly.srvmocker import JsonResponse, MockRoute, start_service


def _make_self_signed_cert(
    tmp_path: Path,
) -> tuple[Path, Path, ssl.SSLContext, ssl.SSLContext]:
    # Use cryptography lib if present; otherwise skip
    pytest.importorskip("cryptography")
    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(x509.NameOID.COMMON_NAME, "localhost")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                    x509.IPAddress(ipaddress.IPv6Address("::1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )

    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert_path, key_path)

    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_ctx.load_verify_locations(cert_path)

    return cert_path, key_path, server_ctx, client_ctx


async def test_start_service_with_tls(tmp_path: Path) -> None:
    _, _, server_ctx, client_ctx = _make_self_signed_cert(tmp_path)
    routes = [MockRoute("GET", "/x", "ok")]
    async with start_service(routes, ssl_context=server_ctx) as service:
        service.register("ok", JsonResponse({"secure": True}))
        assert service.url.scheme == "https"
        connector = TCPConnector(ssl=client_ctx)
        async with ClientSession(connector=connector) as s:
            resp = await s.get(service.url / "x")
            payload = await resp.json()
    assert payload == {"secure": True}
