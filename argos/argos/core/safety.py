"""Salvaguardas de la fase 1.

ARGOS NO opera. No existe ningún módulo de broker ni ninguna ruta que envíe
órdenes. Esta constante es la única fuente de verdad y los tests verifican que
sigue en False y que no hay librerías de broker importadas en el código.

Activar operativa real en el futuro exigirá un cambio de código deliberado,
revisado y con tests propios; nunca una variable de entorno.
"""

LIVE_TRADING_ENABLED: bool = False

DISCLAIMER = (
    "ARGOS es una herramienta de análisis y aprendizaje. Ninguna señal, "
    "interpretación o conclusión garantiza cómo se comportará el mercado. "
    "No es asesoramiento financiero y ARGOS no ejecuta operaciones."
)


class LiveTradingDisabledError(RuntimeError):
    pass


def assert_no_live_trading() -> None:
    """Llamar antes de cualquier acción que pudiera tocar dinero real."""
    if not LIVE_TRADING_ENABLED:
        raise LiveTradingDisabledError(
            "La operativa real está desactivada en ARGOS (fase 1)."
        )
    raise LiveTradingDisabledError("No existe ningún conector de broker implementado.")
