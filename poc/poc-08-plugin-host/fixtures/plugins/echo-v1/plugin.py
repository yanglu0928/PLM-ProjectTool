from __future__ import annotations

import json
import sys


request = json.loads(sys.stdin.readline())
method = request.get("method")
if method == "echo":
    result = {"echo": request.get("params", {}), "implementation": "v1"}
elif method == "version":
    result = {"version": "1.0.0"}
else:
    print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32601, "message": "Method not found"}}))
    raise SystemExit(0)
print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}, ensure_ascii=False))
