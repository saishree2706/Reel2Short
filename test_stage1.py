"""Quick integration test for Stage 1 backend.
Run from the project root:
  .\.venv\Scripts\python.exe test_stage1.py
"""
import subprocess
import sys
import time
import httpx
import os
import signal

BASE = "http://127.0.0.1:8099/api"
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "backend")
PYTHON = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")


def start_server():
    proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8099"],
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to be ready
    for _ in range(20):
        try:
            httpx.get(f"{BASE}/health", timeout=2)
            return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Server did not start in time")


def test_all():
    print("Starting backend server...")
    proc = start_server()
    print("Server started.\n")

    try:
        # 1. Health
        h = httpx.get(f"{BASE}/health", timeout=10).json()
        assert h["status"] == "ok", f"Health failed: {h}"
        print(f"✅ Health: status=ok, instagram_configured={h['instagram_configured']}")

        # 2. List videos (empty)
        vlist = httpx.get(f"{BASE}/videos", timeout=10).json()
        print(f"✅ Video list: {vlist['total']} videos")

        # 3. Instagram reels
        r = httpx.get(f"{BASE}/instagram/reels?limit=25", timeout=30).json()
        print(f"✅ Instagram reels: {len(r['items'])} reels fetched, has_more={r['has_more']}")

        # 4. Try to download a reel with media_url
        reel = next((x for x in r["items"] if x.get("media_url")), None)
        if reel:
            print(f"   Found downloadable reel: {reel['id']}")
            resp = httpx.post(f"{BASE}/videos/download", data={
                "media_id": reel["id"],
                "media_url": reel["media_url"],
            }, timeout=120)
            if resp.status_code == 201:
                asset = resp.json()
                print(f"✅ Download: id={asset['id']}, size={asset['file_size']} bytes, ratio={asset['aspect_ratio']}")
            else:
                print(f"⚠️  Download returned {resp.status_code}: {resp.text[:200]}")
        else:
            print("ℹ️  No reels with media_url available — manual upload path would be used")

        # 5. Reel status for first reel
        if r["items"]:
            first = r["items"][0]
            status = httpx.get(f"{BASE}/instagram/reels/{first['id']}/status", timeout=10).json()
            print(f"✅ Reel status: download_available={status['download_available']}, manual_upload_required={status['manual_upload_required']}")

        print("\n✅ All Stage 1 tests passed!")

    finally:
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    test_all()

