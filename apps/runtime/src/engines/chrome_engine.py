"""Chrome CDP 引擎：通过 Chrome DevTools Protocol 控制浏览器。"""
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import websocket

logger = logging.getLogger("runtime.engines.chrome_engine")

DEFAULT_CHROME_PATH = Path(
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)
DEFAULT_DEBUG_PORT = 9222


class ChromeEngine:
    """Chrome 控制引擎。

    使用 Chrome DevTools Protocol (CDP) 通过 WebSocket 控制浏览器。
    """

    def __init__(
        self,
        exe_path: Optional[Path] = None,
        debug_port: int = DEFAULT_DEBUG_PORT,
    ) -> None:
        self.exe_path = exe_path or DEFAULT_CHROME_PATH
        self.debug_port = debug_port
        self._pid: Optional[int] = None
        self._ws_url: Optional[str] = None
        self._ws: Optional[websocket.WebSocket] = None
        self._cmd_id: int = 0

    def _get_debug_url(self, timeout: float = 10.0) -> Optional[str]:
        """获取 WebSocket 调试 URL。"""
        import urllib.request
        import urllib.error
        import socket

        url = f"http://localhost:{self.debug_port}/json/version"
        tabs_url = f"http://localhost:{self.debug_port}/json"
        start = time.time()
        
        # Wait for port to be open
        while time.time() - start < timeout:
            try:
                with socket.create_connection(("localhost", self.debug_port), timeout=1):
                    break  # Port is open
            except (ConnectionRefusedError, OSError):
                time.sleep(0.5)
        else:
            logger.error(f"CDP port {self.debug_port} never became available")
            return None

        # First try to get a page/tab WebSocket URL
        start = time.time()
        while time.time() - start < timeout:
            try:
                with urllib.request.urlopen(tabs_url, timeout=2) as resp:
                    tabs = json.loads(resp.read().decode())
                    for tab in tabs:
                        if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
                            ws_url = tab["webSocketDebuggerUrl"]
                            logger.info(f"CDP connected to page: {ws_url[:60]}...")
                            return ws_url
                    # Fallback: use first available tab
                    if tabs and tabs[0].get("webSocketDebuggerUrl"):
                        ws_url = tabs[0]["webSocketDebuggerUrl"]
                        logger.info(f"CDP connected to first tab: {ws_url[:60]}...")
                        return ws_url
                    time.sleep(0.5)
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.5)

        # Fallback: browser-level debugger URL (for global commands)
        start = time.time()
        while time.time() - start < timeout:
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    data = json.loads(resp.read().decode())
                    ws_url = data.get("webSocketDebuggerUrl")
                    logger.info(f"CDP connected (browser): {ws_url[:60]}...")
                    return ws_url
            except (urllib.error.URLError, ConnectionError, OSError) as e:
                logger.debug(f"CDP URL fetch failed: {e}")
                time.sleep(0.5)
        logger.error(f"Failed to get webSocketDebuggerUrl within {timeout}s")
        return None

    def _execute_cdp(self, method: str, params: Optional[dict] = None) -> dict:
        """执行 CDP 命令。"""
        if not self._ws:
            if not self._ws_url:
                self._ws_url = self._get_debug_url()
            if not self._ws_url:
                return {"success": False, "error": "无法连接到 Chrome CDP"}

            self._ws = websocket.create_connection(self._ws_url, timeout=10)

        self._cmd_id += 1
        cmd = {
            "id": self._cmd_id,
            "method": method,
            "params": params or {},
        }
        self._ws.send(json.dumps(cmd))
        result = json.loads(self._ws.recv())

        if "error" in result:
            return {
                "success": False,
                "error": result["error"].get("message", "Unknown CDP error"),
            }

        return {"success": True, "result": result.get("result", {})}

    def _close_ws(self) -> None:
        """关闭 WebSocket 连接。"""
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def launch(self, url: str = "about:blank") -> dict:
        """启动 Chrome 并导航到 URL。

        参数：
            url: 初始 URL

        返回：
            {"pid": int, "success": bool, "error": str | None}
        """
        if self.is_running():
            logger.info("Chrome is already running")
            return {
                "pid": self._pid,
                "success": True,
                "error": None,
                "message": "Chrome 已在运行中",
            }

        # Create a temporary user data dir to avoid reusing existing Chrome instances
        import tempfile
        user_data_dir = tempfile.mkdtemp(prefix="chrome_cdp_")
        self._user_data_dir = user_data_dir

        cmd = [
            str(self.exe_path),
            f"--remote-debugging-port={self.debug_port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            url,
        ]

        logger.info(f"Launching Chrome: {' '.join(cmd[:5])}...")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self._pid = proc.pid

            logger.info(f"Chrome started with PID {self._pid}, waiting for CDP...")
            time.sleep(2)
            self._ws_url = self._get_debug_url(timeout=15)

            if self._ws_url:
                return {
                    "pid": self._pid,
                    "success": True,
                    "error": None,
                    "message": "Chrome 启动成功",
                }

            # Log stderr for debugging
            try:
                stderr_output = proc.stderr.read(500).decode("utf-8", errors="replace")
                logger.error(f"Chrome stderr (first 500 chars): {stderr_output}")
            except:
                pass

            return {
                "pid": self._pid,
                "success": False,
                "error": "Chrome 启动但 CDP 未响应",
                "message": "调试端口未响应",
            }
        except FileNotFoundError:
            return {
                "pid": None,
                "success": False,
                "error": f"Chrome 未找到: {self.exe_path}",
                "message": "Chrome 可执行文件不存在",
            }
        except Exception as e:
            return {
                "pid": None,
                "success": False,
                "error": str(e),
                "message": f"Chrome 启动失败: {e}",
            }

    def navigate(self, url: str) -> dict:
        """导航到指定 URL。

        参数：
            url: 目标 URL

        返回：
            {"success": bool, "error": str | None}
        """
        result = self._execute_cdp("Page.navigate", {"url": url})
        if result["success"]:
            time.sleep(2)
            return {
                "success": True,
                "error": None,
                "message": f"已导航到: {url}",
            }
        return result

    def search(self, query: str, engine_url: str = "https://www.google.com/search?q=") -> dict:
        """执行搜索。

        参数：
            query: 搜索关键词
            engine_url: 搜索引擎 URL 模板

        返回：
            {"success": bool, "results": list, "error": str | None}
        """
        import urllib.parse

        search_url = engine_url + urllib.parse.quote(query)
        nav_result = self.navigate(search_url)

        if not nav_result["success"]:
            return nav_result

        time.sleep(2)

        try:
            content = self.extract_content()
            return {
                "success": True,
                "results": [content.get("text", "")],
                "error": None,
                "message": f"搜索完成: {query}",
            }
        except Exception as e:
            return {
                "success": False,
                "results": [],
                "error": str(e),
                "message": "提取搜索结果失败",
            }

    def extract_content(self) -> dict:
        """提取页面正文内容。

        返回：
            {"text": str, "success": bool, "error": str | None}
        """
        # Wait for page to be fully loaded
        time.sleep(2)
        
        js = """
        (function() {
            if (!document || !document.body) return '';
            var clone = document.body.cloneNode(true);
            var removeSelectors = [
                'script', 'style', 'noscript', 'iframe', 'svg',
                'header', 'footer', 'nav', 'aside',
                '.sidebar', '.nav', '.footer', '.header',
                '[role="navigation"]', '[role="complementary"]'
            ];
            for (var i = 0; i < removeSelectors.length; i++) {
                var els = clone.querySelectorAll(removeSelectors[i]);
                for (var j = 0; j < els.length; j++) {
                    els[j].parentNode.removeChild(els[j]);
                }
            }
            return (clone.innerText || clone.textContent || '');
        })();
        """
        result = self._execute_cdp(
            "Runtime.evaluate",
            {"expression": js, "returnByValue": True},
        )

        if result["success"]:
            cdp_result = result["result"]
            eval_result = cdp_result.get("result", {})
            text = eval_result.get("value", "")
            if not isinstance(text, str):
                text = str(text) if text else ""
            logger.info(f"Content extracted: {len(text)} chars")
            return {
                "text": text[:5000],
                "success": True,
                "error": None,
                "message": "内容提取成功",
            }
        return {
            "text": "",
            "success": False,
            "error": result.get("error", "执行 JS 失败"),
        }

    def screenshot(self, path: str = "") -> dict:
        """截图。

        参数：
            path: 保存路径（可选）

        返回：
            {"success": bool, "path": str, "error": str | None}
        """
        result = self._execute_cdp(
            "Page.captureScreenshot",
            {"format": "png"},
        )

        if result["success"]:
            import base64

            data = result["result"].get("data", "")
            if path:
                output_path = Path(path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(data))
                return {
                    "success": True,
                    "path": str(output_path),
                    "error": None,
                }
            return {
                "success": True,
                "path": "",
                "error": None,
                "data_length": len(data),
            }
        return result

    def is_running(self) -> bool:
        """检查 Chrome 是否正在运行。"""
        try:
            import psutil

            if self._pid:
                try:
                    proc = psutil.Process(self._pid)
                    return proc.is_running() and "chrome" in proc.name().lower()
                except psutil.NoSuchProcess:
                    return False

            for proc in psutil.process_iter(["name", "exe"]):
                try:
                    exe = proc.info.get("exe", "")
                    if exe and "chrome.exe" in str(exe).lower():
                        self._pid = proc.pid
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except ImportError:
            return False

    def close(self) -> dict:
        """关闭 Chrome。

        返回：
            {"success": bool, "error": str | None}
        """
        self._close_ws()

        if not self._pid:
            return {
                "success": True,
                "error": None,
                "message": "Chrome 未运行",
            }

        try:
            import psutil

            proc = psutil.Process(self._pid)
            proc.terminate()
            proc.wait(timeout=5)
            self._pid = None
            return {
                "success": True,
                "error": None,
                "message": "Chrome 已关闭",
            }
        except psutil.NoSuchProcess:
            self._pid = None
            return {
                "success": True,
                "error": None,
                "message": "Chrome 已关闭",
            }
        except psutil.TimeoutExpired:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(self._pid)],
                    capture_output=True,
                    timeout=5,
                )
                self._pid = None
                return {
                    "success": True,
                    "error": None,
                    "message": "Chrome 已强制关闭",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "message": f"关闭 Chrome 失败: {e}",
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"关闭 Chrome 失败: {e}",
            }
