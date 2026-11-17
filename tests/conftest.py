import sys
import types
from pathlib import Path

_PKG = "ginko_pure"
if _PKG not in sys.modules:
    pkg = types.ModuleType(_PKG)
    pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components" / "ginko")]
    sys.modules[_PKG] = pkg
