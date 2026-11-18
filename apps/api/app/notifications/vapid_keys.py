"""Generate Web Push VAPID keys without writing any secret into the repository.

Run: python -m app.notifications.vapid_keys --output-dir /secure/path
"""
import argparse
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    target = Path(args.output_dir).expanduser().resolve()
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_file = target / "sentico-vapid-private.pem"
    if private_file.exists():
        raise SystemExit(f"Chave já existente: {private_file}. Não substitua sem planejar a reinscrição dos celulares.")
    key = ec.generate_private_key(ec.SECP256R1())
    payload = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    fd = os.open(private_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(payload)
    point = key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public = base64.urlsafe_b64encode(point).decode().rstrip("=")
    print("PUSH_VAPID_PUBLIC_KEY=" + public)
    print("PUSH_VAPID_SUBJECT=mailto:EMAIL_RESPONSAVEL_PELO_DOMINIO")
    print("Arquivo privado (não publicar nem enviar): " + str(private_file))
    print("Guarde este arquivo privado em /app/secrets/sentico-vapid-private.pem no container API (volume somente leitura).")


if __name__ == "__main__":
    main()
