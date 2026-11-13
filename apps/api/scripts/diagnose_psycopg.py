from __future__ import annotations

import argparse
import asyncio
import socket
import statistics
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg

from app.core.config import settings


@dataclass(frozen=True)
class Measurement:
    label: str
    samples: tuple[float, ...]

    @property
    def minimum(self) -> float:
        return min(self.samples)

    @property
    def median(self) -> float:
        return statistics.median(self.samples)

    @property
    def maximum(self) -> float:
        return max(self.samples)


def psycopg_dsn(*, sslmode: str | None = None) -> str:
    raw_dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlsplit(raw_dsn)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    if sslmode is not None:
        query["sslmode"] = sslmode

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


def connection_target() -> tuple[str, int]:
    parsed = urlsplit(psycopg_dsn())
    return parsed.hostname or "127.0.0.1", parsed.port or 5432


def measure_tcp(samples: int, timeout: float) -> Measurement:
    host, port = connection_target()
    elapsed_samples: list[float] = []

    for _ in range(samples):
        started_at = time.perf_counter()
        with socket.create_connection((host, port), timeout=timeout):
            pass
        elapsed_samples.append(time.perf_counter() - started_at)

    return Measurement("TCP", tuple(elapsed_samples))


def measure_sync(samples: int, timeout: int, sslmode: str) -> Measurement:
    elapsed_samples: list[float] = []

    for _ in range(samples):
        started_at = time.perf_counter()
        with psycopg.connect(
            psycopg_dsn(sslmode=sslmode),
            connect_timeout=timeout,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

        if result != (1,):
            raise RuntimeError(f"Resultado síncrono inesperado: {result!r}")

        elapsed_samples.append(time.perf_counter() - started_at)

    return Measurement(f"Psycopg síncrono (sslmode={sslmode})", tuple(elapsed_samples))


async def measure_async(samples: int, timeout: int, sslmode: str) -> Measurement:
    elapsed_samples: list[float] = []

    for _ in range(samples):
        started_at = time.perf_counter()
        connection = await psycopg.AsyncConnection.connect(
            psycopg_dsn(sslmode=sslmode),
            connect_timeout=timeout,
        )

        try:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
        finally:
            await connection.close()

        if result != (1,):
            raise RuntimeError(f"Resultado assíncrono inesperado: {result!r}")

        elapsed_samples.append(time.perf_counter() - started_at)

    return Measurement(f"Psycopg assíncrono (sslmode={sslmode})", tuple(elapsed_samples))


def print_measurement(measurement: Measurement) -> None:
    samples = ", ".join(f"{value:.3f}s" for value in measurement.samples)
    print(f"\n{measurement.label}")
    print(f"  amostras: {samples}")
    print(f"  mínimo:   {measurement.minimum:.3f}s")
    print(f"  mediana:  {measurement.median:.3f}s")
    print(f"  máximo:   {measurement.maximum:.3f}s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnóstico direto da conexão PostgreSQL/Psycopg."
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=3,
        help="Quantidade de medições por cenário.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Timeout de conexão em segundos.",
    )
    return parser.parse_args()


async def run_async_measurements(samples: int, timeout: int) -> list[Measurement]:
    return [
        await measure_async(samples, timeout, "prefer"),
        await measure_async(samples, timeout, "disable"),
    ]


def main() -> None:
    args = parse_args()
    if args.samples < 1:
        raise SystemExit("--samples deve ser maior que zero.")

    host, port = connection_target()
    print("Diagnóstico direto do PostgreSQL")
    print(f"Destino: {host}:{port}")
    print("A senha e a URL completa não são exibidas.")

    measurements: list[Measurement] = []

    try:
        measurements.append(measure_tcp(args.samples, float(args.timeout)))
        measurements.append(measure_sync(args.samples, args.timeout, "prefer"))
        measurements.append(measure_sync(args.samples, args.timeout, "disable"))
        measurements.extend(
            asyncio.run(
                run_async_measurements(args.samples, args.timeout),
                loop_factory=asyncio.SelectorEventLoop,
            )
        )
    except Exception as exc:
        print(f"\nFalha durante o diagnóstico: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc

    for measurement in measurements:
        print_measurement(measurement)

    print("\nLeitura rápida:")
    print(
        "- TCP lento: investigar Windows, firewall, VPN e "
        "encaminhamento de porta do Docker."
    )
    print(
        "- TCP rápido e Psycopg lento: investigar autenticação, SSL "
        "e handshake PostgreSQL."
    )
    print(
        "- sslmode=disable muito mais rápido: manter SSL desativado "
        "apenas no desenvolvimento local."
    )
    print(
        "- síncrono e assíncrono semelhantes: o atraso não está no "
        "SQLAlchemy nem no event loop."
    )


if __name__ == "__main__":
    main()
