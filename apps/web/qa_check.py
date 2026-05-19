import httpx

print("=== Frontend Check ===")
try:
    r = httpx.get("http://localhost:5173/", timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Body length: {len(r.text)}")
    title_ok = "Local AI" in r.text or "local-auto" in r.text.lower()
    print(f"Title found: {title_ok}")
    print("Frontend serving correctly" if r.status_code == 200 and len(r.text) > 100 else "Frontend issue")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Backend Check ===")
try:
    r = httpx.get("http://127.0.0.1:8000/api/health", timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.json()}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Proxy Check (frontend -> backend) ===")
try:
    r = httpx.get("http://localhost:5173/api/health", timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.json()}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== App List via Proxy ===")
try:
    r = httpx.get("http://localhost:5173/api/apps", timeout=5)
    print(f"Status: {r.status_code}")
    apps = r.json()
    print(f"Apps count: {len(apps)}")
    for app in apps:
        print(f"  - {app['app_id']}: {app['display_name']}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Task Creation via Proxy ===")
try:
    r = httpx.post("http://localhost:5173/api/tasks", json={"user_input": "test qa task"}, timeout=5)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Task: {data}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== App Launch via Proxy ===")
try:
    r = httpx.post("http://localhost:5173/api/apps/launch", json={"app_id": "file_explorer"}, timeout=5)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Launch result: {data}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Profile Check via Proxy ===")
try:
    r = httpx.get("http://localhost:5173/api/apps/vscode/profile", timeout=5)
    print(f"Status: {r.status_code}")
    data = r.json()
    if data:
        print(f"Profile: {data['display_name']} (method: {data['automation_method']})")
    else:
        print("Profile: null")
except Exception as e:
    print(f"Error: {e}")
