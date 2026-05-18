"""Debug chrome extract_content."""
import sys
sys.path.insert(0, "src")

from engines.chrome_engine import ChromeEngine
import logging

logging.basicConfig(level=logging.DEBUG)

engine = ChromeEngine(debug_port=9223)  # Use different port
print("=== Launching ===")
launch = engine.launch("about:blank")
print(f"Launch: {launch}")

print("=== Navigating ===")
nav = engine.navigate("https://www.example.com")
print(f"Navigate: {nav}")

import time
time.sleep(3)

print("=== Debugging WS URL ===")
print(f"WS URL: {engine._ws_url[:80]}...")

print("=== Extracting ===")
extract = engine.extract_content()
print(f"Extract success: {extract['success']}")
print(f"Extract text length: {len(extract.get('text', ''))}")
print(f"Extract text preview: {extract.get('text', '')[:200]}")

print("=== Raw CDP test ===")
import json
js = "document.body.innerText.substring(0, 50)"
r = engine._execute_cdp("Runtime.evaluate", {"expression": js, "returnByValue": True})
print(f"Raw CDP: {json.dumps(r, indent=2)[:500]}")

engine.close()
print("=== Done ===")
