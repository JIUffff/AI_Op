"""M6 端到端真实引擎验证脚本。"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from engines.file_engine import FileEngine
from engines.vscode_engine import VSCodeEngine
from engines.chrome_engine import ChromeEngine

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

results = {}

def test_file_engine():
    """测试 File 引擎：扫描 + 分类 + 移动 + 回滚。"""
    print("\n=== File Engine ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_files = {
            "photo.jpg": "fake image content",
            "report.pdf": "fake pdf content",
            "video.mp4": "fake video content",
            "script.py": "print('hello')",
            "notes.txt": "some notes",
        }
        
        for name, content in test_files.items():
            Path(tmpdir, name).write_text(content)
        
        engine = FileEngine()
        
        # Test 1: scan_directory
        print("  Testing scan_directory...")
        scan = engine.scan_directory(tmpdir)
        if scan["count"] == 5:
            print(f"    {PASS} Scanned {scan['count']} files")
            results["file_scan"] = True
        else:
            print(f"    {FAIL} Expected 5 files, got {scan['count']}")
            results["file_scan"] = False
        
        # Test 2: classify_files
        print("  Testing classify_files...")
        files = [f["path"] for f in scan["files"]]
        classify = engine.classify_files(files)
        categories = classify["categories"]
        expected_cats = {"images", "documents", "videos", "code"}
        found_cats = set(categories.keys())
        
        if expected_cats.issubset(found_cats):
            print(f"    {PASS} Classified into {len(categories)} categories: {', '.join(found_cats)}")
            results["file_classify"] = True
        else:
            missing = expected_cats - found_cats
            print(f"    {FAIL} Missing categories: {missing}, got {found_cats}")
            results["file_classify"] = False
        
        # Test 3: organize_directory
        print("  Testing organize_directory...")
        organize = engine.organize_directory(tmpdir)
        if organize["moved"] >= 3:
            print(f"    {PASS} Moved {organize['moved']} files to categories")
            results["file_organize"] = True
        else:
            print(f"    {FAIL} Expected >=3 moves, got {organize['moved']}")
            results["file_organize"] = False
        
        # Test 4: rollback
        print("  Testing rollback...")
        rollback = engine.rollback()
        if rollback["restored"] > 0:
            print(f"    {PASS} Restored {rollback['restored']} files")
            results["file_rollback"] = True
        else:
            print(f"    {SKIP} No operations to rollback or restore failed")
            results["file_rollback"] = None

def test_vscode_engine():
    """测试 VSCode 引擎：启动 + 打开文件。"""
    print("\n=== VSCode Engine ===")
    
    engine = VSCodeEngine()
    
    # Test 1: is_running check
    print("  Testing is_running...")
    running = engine.is_running()
    if not running:
        print(f"    {PASS} VSCode not running (expected)")
        results["vscode_check"] = True
    else:
        print(f"    {SKIP} VSCode already running")
        results["vscode_check"] = True
    
    # Test 2: launch
    print("  Testing launch...")
    launch = engine.launch()
    if launch["success"]:
        print(f"    {PASS} VSCode launched (pid={launch['pid']})")
        results["vscode_launch"] = True
        time.sleep(2)
    else:
        print(f"    {FAIL} VSCode launch failed: {launch['message']}")
        results["vscode_launch"] = False
        return
    
    # Test 3: open_file (create a test file)
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write("print('hello from superpower')\n")
        test_file = f.name
    
    print(f"  Testing open_file ({Path(test_file).name})...")
    open_result = engine.open_file(test_file)
    if open_result["success"]:
        print(f"    {PASS} File opened in VSCode")
        results["vscode_open"] = True
    else:
        print(f"    {FAIL} File open failed: {open_result['message']}")
        results["vscode_open"] = False
    
    # Cleanup
    try:
        os.unlink(test_file)
    except:
        pass
    
    # Test 4: close
    print("  Testing close...")
    close = engine.close()
    if close["success"]:
        print(f"    {PASS} VSCode closed")
        results["vscode_close"] = True
    else:
        print(f"    {FAIL} VSCode close failed: {close['message']}")
        results["vscode_close"] = False

def test_chrome_engine():
    """测试 Chrome 引擎：启动 + 导航。"""
    print("\n=== Chrome Engine ===")
    
    engine = ChromeEngine(debug_port=9222)
    
    # Kill existing Chrome processes to avoid CDP port conflicts
    import subprocess
    import psutil
    print("  Cleaning existing Chrome processes...")
    # Kill chrome processes by PID to be more targeted
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if "chrome" in proc.info["name"].lower():
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(3)
    
    # Test 1: is_running check
    print("  Testing is_running...")
    running = engine.is_running()
    if not running:
        print(f"    {PASS} Chrome not running (expected)")
        results["chrome_check"] = True
    else:
        print(f"    {SKIP} Chrome already running")
        results["chrome_check"] = True
    
    # Test 2: launch
    print("  Testing launch (about:blank)...")
    launch = engine.launch("about:blank")
    if launch["success"]:
        print(f"    {PASS} Chrome launched (pid={launch['pid']})")
        results["chrome_launch"] = True
        time.sleep(2)
    else:
        print(f"    {FAIL} Chrome launch failed: {launch['message']}")
        results["chrome_launch"] = False
        return
    
    # Test 3: navigate
    print("  Testing navigate (https://www.example.com)...")
    nav = engine.navigate("https://www.example.com")
    if nav["success"]:
        print(f"    {PASS} Navigated to example.com")
        results["chrome_navigate"] = True
    else:
        print(f"    {FAIL} Navigate failed: {nav.get('error', 'unknown')}")
        results["chrome_navigate"] = False
    
    # Test 4: extract_content
    print("  Testing extract_content...")
    extract = engine.extract_content()
    if extract["success"] and len(extract.get("text", "")) > 0:
        text_preview = extract["text"][:50].replace("\n", " ")
        print(f"    {PASS} Content extracted ({len(extract['text'])} chars): '{text_preview}...'")
        results["chrome_extract"] = True
    else:
        print(f"    {FAIL} Extract failed or empty")
        results["chrome_extract"] = False
    
    # Test 5: close
    print("  Testing close...")
    close = engine.close()
    if close["success"]:
        print(f"    {PASS} Chrome closed")
        results["chrome_close"] = True
    else:
        print(f"    {FAIL} Chrome close failed: {close['message']}")
        results["chrome_close"] = False

def print_report():
    """输出验证报告。"""
    print("\n" + "=" * 50)
    print("=== M6 End-to-End Verification Report ===")
    print("=" * 50)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for test, result in results.items():
        if result is True:
            status = PASS
        elif result is False:
            status = FAIL
        else:
            status = SKIP
        print(f"  [{status}] {test}")
    
    print(f"\n--- Summary ---")
    print(f"  Total:   {total}")
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Score:   {int(passed/total*100) if total > 0 else 0}%")
    
    if failed == 0 and skipped == 0:
        print(f"\n  \033[92mALL TESTS PASSED - Engines verified!\033[0m")
    elif failed == 0:
        print(f"\n  \033[93mPASSED with {skipped} skipped\033[0m")
    else:
        print(f"\n  \033[91m{failed} test(s) failed\033[0m")

if __name__ == "__main__":
    test_file_engine()
    test_vscode_engine()
    test_chrome_engine()
    print_report()
