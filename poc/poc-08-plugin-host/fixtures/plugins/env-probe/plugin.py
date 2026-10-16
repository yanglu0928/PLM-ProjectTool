from __future__ import annotations

import json
import os
import sys


request = json.loads(sys.stdin.readline())
sensitive_names = ["DATABASE_URL", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "KEY"]
result = {"visible": {name: name in os.environ for name in sensitive_names}}
print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}))
