"""
Entry point for python -m adeline

IMPORTANTE: env_setup debe importarse PRIMERO para configurar variables de
entorno antes de que cualquier módulo importe inference.
"""
# ============================================================================
# STEP 1: Setup environment (disable models BEFORE any other imports)
# ============================================================================
from . import env_setup  # noqa: F401 - side effect: configures os.environ

# ============================================================================
# STEP 2: NOW import and run main (models already disabled via env vars)
# ============================================================================
if __name__ == "__main__":
    from .app import main
    main()
