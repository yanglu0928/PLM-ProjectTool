from __future__ import annotations

import json
import sys


request = json.loads(sys.stdin.readline())
print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": {"unexpected": True}}))
