import urllib.request, urllib.parse, sys

url = "https://55419dfb-8584-4c25-bc6f-88dd66dd8614-00-2pphew93rme1e.pike.replit.dev/voice"
data = urllib.parse.urlencode({}).encode()
req = urllib.request.Request(url, data=data, method="POST")
req.add_header("User-Agent", "curl/7.64")
try:
  with urllib.request.urlopen(req, timeout=10) as resp:
    print("HTTP", resp.status)
    print(resp.read().decode("utf-8", errors="replace"))
except Exception as e:
  print("ERROR:", e)
  sys.exit(1)
