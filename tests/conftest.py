import sys
from pathlib import Path
import types

# Ensure project root is importable during tests
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Provide a stub yfinance module if it's not installed in the test environment
if "yfinance" not in sys.modules:
    stub = types.ModuleType("yfinance")
    def _stub_search(_query):
        raise RuntimeError("stub yfinance.search should be patched in tests")
    stub.search = _stub_search
    sys.modules["yfinance"] = stub

# Provide a stub loguru.logger if loguru isn't installed
if "loguru" not in sys.modules:
    loguru_stub = types.ModuleType("loguru")
    class _Logger:
        def __getattr__(self, _):
            # Return a no-op function for any logger method
            def _noop(*args, **kwargs):
                pass
            return _noop
    loguru_stub.logger = _Logger()
    sys.modules["loguru"] = loguru_stub
