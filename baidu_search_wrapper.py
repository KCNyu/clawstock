import json
import os
import subprocess
import sys

if len(sys.argv) < 2:
    print("usage: python3 baidu_search_wrapper.py <query> [count]", file=sys.stderr)
    sys.exit(2)

query = sys.argv[1]
count = int(sys.argv[2]) if len(sys.argv) > 2 else 8
payload = json.dumps({"query": query, "count": count}, ensure_ascii=False)
script = "/root/skills/baidu-search/scripts/search.py"

result = subprocess.run([
    "python3",
    script,
    payload,
], env=os.environ.copy(), capture_output=True, text=True)

if result.stdout:
    print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)

sys.exit(result.returncode)
