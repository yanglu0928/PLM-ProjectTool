from __future__ import annotations

import json
import sys
import time


request = json.loads(sys.stdin.readline())
time.sleep(5)
print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": {"late": True}}))
