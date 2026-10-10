"""Descarga y conversión de históricos de Tiingo para los experimentos de ARGOS.

    python -m argos.tools.tiingo descargar   # 1. baja los originales a data/raw/tiingo/ (necesita TIINGO_API_KEY)
    python -m argos.tools.tiingo convertir   # 2. los convierte (EXP-001: data/csv/; EXP-00N: data/csv/EXP-00N/) y los valida
    python -m argos.tools.tiingo diagnosticar-tls  # comprueba solo la conexión TLS (sin clave ni datos)

Activos y fechas salen del protocolo (por defecto EXP-001, activos principales):
no se pueden cambiar desde aquí. La clave solo se lee de la variable TIINGO_API_KEY.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from argos.data.sources import tiingo
from argos.experiments.protocol import load_protocol


def _plan(protocol_id: str, tickers: list[str] | None, include_complementary: bool):
    protocol, _, _ = load_protocol(protocol_id)
    allowed = [a.ticker for a in protocol.assets if a.core or include_complementary]
    chosen = [t.upper() for t in tickers] if tickers else allowed
    outside = [t for t in chosen if t not in [a.ticker for a in protocol.assets]]
    if outside:
        raise tiingo.TiingoError(f"{outside} no están en el protocolo {protocol_id}. Solo se descargan activos del protocolo.")
    req = protocol.data_requirements
    return chosen, date.fromisoformat(req["required_start"]), date.fromisoformat(req["required_end"])


def cmd_descargar(args) -> int:
    tickers, start, end = _plan(args.protocolo, args.tickers, args.complementarios)
    key = tiingo.read_api_key()  # se detiene aquí si falta la variable
    print(f"Descargando {', '.join(tickers)} · {start} → {end} · destino {tiingo.RAW_DIR}")
    failed = 0
    for t in tickers:
        try:
            rec = tiingo.download_ticker(t, start, end, key=key, allow_new=args.nueva_descarga)
        except tiingo.AlreadyDownloadedError as exc:
            print(f"  = {exc}")
            continue
        except (tiingo.TiingoAuthError, tiingo.TiingoTLSError) as exc:
            print(f"  ✕ {exc}")
            print("Se detiene la descarga: sin una conexión verificada y autenticada no tiene sentido seguir.")
            return 2
        except tiingo.TiingoError as exc:
            print(f"  ✕ {exc}")
            failed += 1
            continue
        print(f"  ✓ {t}: {rec.rows} sesiones {rec.first_date} → {rec.last_date} · {rec.raw_file} · SHA-256 {rec.sha256[:16]}…")
    if failed:
        print(f"{failed} activo(s) con error. No se ha guardado nada para ellos.")
        return 1
    print("Originales guardados sin modificar. Siguiente paso: python -m argos.tools.tiingo convertir")
    return 0


def cmd_convertir(args) -> int:
    from argos.experiments.storage import check_csv_dir, csv_dir_for, download_for_range

    tickers, start, end = _plan(args.protocolo, args.tickers, args.complementarios)
    csv_dir = csv_dir_for(args.protocolo)
    check_csv_dir(args.protocolo, csv_dir)
    print(f"Convirtiendo para {args.protocolo} → {csv_dir}")
    failed = 0
    for t in tickers:
        try:
            # Solo la descarga con el rango EXACTO de este protocolo: la de otro experimento nunca se mezcla.
            entry = download_for_range(t, start, end, tiingo.RAW_DIR)
            res = tiingo.convert(t, overwrite=args.sobrescribir, raw_dir=tiingo.RAW_DIR, csv_dir=csv_dir, entry=entry)
        except tiingo.TiingoError as exc:
            print(f"  ✕ {exc}")
            failed += 1
            continue
        splits = ", ".join(f"{d} ×{f}" for d, f in res.splits) or "ninguno"
        divs = ", ".join(f"{y}:{n}" for y, n in res.dividends_per_year.items()) or "ninguno"
        print(f"  ✓ {t}: {res.rows} sesiones → {res.csv_file.name} (+ {res.source_file.name})")
        print(f"      splits según Tiingo: {splits}")
        print(f"      dividendos por año según Tiingo: {divs}")
    if failed:
        print(f"{failed} activo(s) sin convertir. Revisa los mensajes anteriores.")
        return 1
    print("\nControl de integridad con los requisitos del protocolo:")
    from argos.data.check import main as check_main

    return check_main(["--protocolo", args.protocolo, "--dir", str(csv_dir), *tickers])


def cmd_diagnosticar_tls(_args) -> int:
    ok, lines = tiingo.diagnose_tls()
    print(f"Diagnóstico TLS de {tiingo.API_HOST} (sin clave, sin descargar datos):")
    for line in lines:
        print(f"  {line}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m argos.tools.tiingo", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in (("descargar", cmd_descargar, "Descarga los originales de Tiingo (no los modifica)."),
                            ("convertir", cmd_convertir, "Convierte los originales al formato de ARGOS y los valida.")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--protocolo", default="EXP-001")
        p.add_argument("--tickers", nargs="*", help="Subconjunto de activos del protocolo (por defecto, los principales).")
        p.add_argument("--complementarios", action="store_true", help="Incluir también los activos complementarios.")
        if name == "descargar":
            p.add_argument("--nueva-descarga", action="store_true",
                           help="Descargar otra versión aunque ya exista una descarga válida del mismo rango.")
        if name == "convertir":
            p.add_argument("--sobrescribir", action="store_true", help="Reemplazar un CSV existente con contenido distinto.")
        p.set_defaults(fn=fn)
    diag = sub.add_parser("diagnosticar-tls", help="Comprueba la conexión TLS con Tiingo (sin clave ni datos).")
    diag.set_defaults(fn=cmd_diagnosticar_tls)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except tiingo.TiingoError as exc:
        print(f"✕ {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
