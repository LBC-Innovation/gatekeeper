import sys
from pathlib import Path

# The service package lives next to tests/. Put it first so `import gatekeeper` finds this copy.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import the service package now, so scripts that add the v1 server folder to sys.path reuse this copy.
import gatekeeper.core  # noqa: E402,F401
