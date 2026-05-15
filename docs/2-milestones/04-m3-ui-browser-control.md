# 04 - M3 UI 感知与浏览器控制

对应总文档第 11 节 M3（第 6-7 周）
前置文档：[../1-standards/00-project-overview.md](../1-standards/00-project-overview.md)、[../2-milestones/03-m2-file-permission-audit.md](../2-milestones/03-m2-file-permission-audit.md)

---

## 0. 本阶段目标

实现 UIA 基础读取与元素定位、Playwright + CDP 浏览器控制链、Ollama Vision 兜底接口。交付物：三类基础 UI 操作可稳定执行，视觉只作兜底且可验证。

---

## 1. 全局规则速查

- 控制路径优先级：CLI/API > 文件系统 > Accessibility > DOM/CDP > Vision > 鼠标键盘
- Vision 只作兜底，必须可验证
- 元素定位必须组合：语义 + 层级 + 相对位置 + 验证
- 每步操作必须有 expect + verify

---

## 2. 本阶段架构

```
apps/runtime/
  src/
    engines/
      uia_engine.py          # Windows UI Automation 读取
      browser_engine.py      # Playwright + CDP 浏览器控制
      vision_engine.py       # Ollama Vision 兜底
    mcp_tools/
      uia_read.py            # MCP 工具: 读取 UI 元素
      uia_click.py           # MCP 工具: 点击 UI 元素
      uia_type.py            # MCP 工具: 输入文本
      browser_navigate.py    # MCP 工具: 导航到 URL
      browser_click.py       # MCP 工具: 点击页面元素
      browser_extract.py     # MCP 工具: 提取页面内容
      vision_describe.py     # MCP 工具: 描述屏幕内容
      vision_ocr.py          # MCP 工具: OCR 识别
```

---

## 3. UIA Engine

### 3.1 功能

| 功能 | 说明 |
|------|------|
| 获取 UI 树 | 读取指定窗口的 UI Automation 树 |
| 元素定位 | 按名称/类型/自动化 ID/层级定位元素 |
| 元素操作 | 点击、输入、获取值 |
| 状态验证 | 检查元素是否可见/可交互/包含特定文本 |

### 3.2 实现骨架

```python
# apps/runtime/src/engines/uia_engine.py

import logging
import time
from typing import Optional
import uiautomation as auto

logger = logging.getLogger("runtime.uia_engine")

class UIAEngine:
    """Windows UI Automation 引擎。"""
    
    def get_ui_tree(self, window_title: str, max_depth: int = 5) -> dict:
        """获取指定窗口的 UI 树。
        
        Returns:
            嵌套的 UI 元素字典
        """
        window = auto.WindowControl(searchDepth=1, Name=window_title)
        if not window.Exists(1, 0):
            return {"error": f"窗口 '{window_title}' 未找到", "code": "E4004"}
        
        return self._serialize_element(window, max_depth, 0)
    
    def _serialize_element(self, ctrl, max_depth: int, current_depth: int) -> dict:
        """序列化 UIA 元素为字典。"""
        if current_depth > max_depth:
            return None
        
        element = {
            "control_type": ctrl.ControlTypeName,
            "name": ctrl.Name,
            "automation_id": ctrl.AutomationId,
            "class_name": ctrl.ClassName,
            "rect": {
                "x": ctrl.BoundingRectangle.left,
                "y": ctrl.BoundingRectangle.top,
                "width": ctrl.BoundingRectangle.width(),
                "height": ctrl.BoundingRectangle.height(),
            },
            "is_enabled": ctrl.IsEnabled,
            "is_visible": ctrl.IsVisible,
            "value": self._get_value(ctrl),
        }
        
        children = []
        for child in ctrl.GetChildren():
            serialized = self._serialize_element(child, max_depth, current_depth + 1)
            if serialized:
                children.append(serialized)
        
        if children:
            element["children"] = children
        
        return element
    
    def _get_value(self, ctrl) -> Optional[str]:
        """获取元素值。"""
        try:
            if isinstance(ctrl, auto.EditControl):
                return ctrl.GetValuePattern().Value
            elif isinstance(ctrl, auto.TextControl):
                return ctrl.Name
        except Exception:
            pass
        return None
    
    def find_element(self, window_title: str, **criteria) -> Optional[dict]:
        """查找 UI 元素。
        
        支持条件：name, automation_id, control_type, class_name
        
        组合策略：语义(name) + 层级(control_type) + 属性(automation_id)
        """
        window = auto.WindowControl(searchDepth=1, Name=window_title)
        if not window.Exists(1, 0):
            return None
        
        search_ctrl = self._build_search_criteria(window, criteria)
        
        if search_ctrl.Exists(2, 0.5):
            return self._serialize_element(search_ctrl, 0, 0)
        
        return None
    
    def _build_search_criteria(self, parent, criteria: dict):
        """构建搜索条件。"""
        # 优先级：automation_id > name + control_type > name
        automation_id = criteria.get("automation_id")
        name = criteria.get("name")
        control_type = criteria.get("control_type")
        
        if automation_id:
            return auto.Control(searchDepth=5, AutomationId=automation_id)
        elif name and control_type:
            return auto.Control(searchDepth=5, Name=name, ControlType=control_type)
        elif name:
            return auto.Control(searchDepth=5, Name=name)
        else:
            raise ValueError("至少需要提供一个搜索条件")
    
    def click_element(self, window_title: str, **criteria) -> dict:
        """点击 UI 元素。权限 L4。"""
        element = self.find_element(window_title, **criteria)
        if not element:
            return {"success": False, "error": {"code": "E4004", "message": "元素未找到"}}
        
        try:
            ctrl = self._resolve_control(window_title, criteria)
            ctrl.Click()
            return {"success": True, "result": {"clicked": element["name"]}}
        except Exception as e:
            return {"success": False, "error": {"code": "E4005", "message": str(e)}}
    
    def type_text(self, window_title: str, text: str, **criteria) -> dict:
        """在 UI 元素中输入文本。权限 L4。"""
        try:
            ctrl = self._resolve_control(window_title, criteria)
            ctrl.SendKeys(text)
            return {"success": True, "result": {"typed": text}}
        except Exception as e:
            return {"success": False, "error": {"code": "E4005", "message": str(e)}}
    
    def verify_element(self, window_title: str, expected_state: dict, timeout: float = 5.0) -> dict:
        """验证 UI 元素状态。
        
        Args:
            expected_state: {"name": "提交", "visible": True, "enabled": True}
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            element = self.find_element(window_title, **{
                k: v for k, v in expected_state.items() if k in ("name", "automation_id", "control_type")
            })
            
            if element:
                # 验证状态
                if expected_state.get("visible") and not element.get("is_visible"):
                    time.sleep(0.3)
                    continue
                if expected_state.get("enabled") and not element.get("is_enabled"):
                    time.sleep(0.3)
                    continue
                return {"success": True, "result": {"state": element}}
            
            time.sleep(0.3)
        
        return {"success": False, "error": {"code": "E4005", "message": "元素状态验证超时"}}
    
    def _resolve_control(self, window_title: str, criteria: dict):
        """解析为 UIA 控件对象。"""
        window = auto.WindowControl(searchDepth=1, Name=window_title)
        return self._build_search_criteria(window, criteria)
```

---

## 4. Browser Engine (Playwright + CDP)

### 4.1 功能

| 功能 | 说明 | 权限级别 |
|------|------|---------|
| 导航到 URL | 打开/跳转页面 | L3 |
| 等待元素 | 等待页面元素出现 | L3 |
| 点击元素 | CSS 选择器点击 | L4 |
| 输入文本 | 在表单中输入 | L4 |
| 提取内容 | 提取正文/标题/链接 | L1 |
| 截图 | 页面截图（用于 Vision 兜底） | L3 |
| 获取控制台日志 | 捕获页面 JS 日志 | L0 |

### 4.2 实现骨架

```python
# apps/runtime/src/engines/browser_engine.py

import logging
import time
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser

logger = logging.getLogger("runtime.browser_engine")

class BrowserEngine:
    """Playwright 浏览器控制引擎（CDP 模式）。"""
    
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
    
    async def connect(self, chrome_path: str = None, cdp_port: int = 9222):
        """连接到 Chrome（CDP 模式）。"""
        self._playwright = await async_playwright().start()
        
        # 方式一：连接到已有 Chrome（CDP）
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{cdp_port}"
            )
            contexts = self._browser.contexts
            if contexts:
                self._page = contexts[0].pages[0] if contexts[0].pages else await contexts[0].new_page()
            else:
                context = await self._browser.new_context()
                self._page = await context.new_page()
            logger.info("已连接到 Chrome CDP")
            return
        except Exception as e:
            logger.warning(f"CDP 连接失败: {e}，回退到启动新实例")
        
        # 方式二：启动新 Chrome 实例
        self._browser = await self._playwright.chromium.launch(
            executable_path=chrome_path,
            headless=False,
            args=["--remote-debugging-port=9222"],
        )
        context = await self._browser.new_context()
        self._page = await context.new_page()
    
    async def navigate(self, url: str, wait_until: str = "load", timeout_ms: int = 30000) -> dict:
        """导航到 URL。权限 L3。"""
        try:
            await self._page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            return {
                "success": True,
                "result": {
                    "url": self._page.url,
                    "title": await self._page.title(),
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "E4006", "message": str(e)}}
    
    async def wait_for_selector(self, selector: str, timeout_ms: int = 10000) -> dict:
        """等待元素出现。"""
        try:
            await self._page.wait_for_selector(selector, timeout=timeout_ms)
            return {"success": True, "result": {"selector": selector, "found": True}}
        except Exception as e:
            return {"success": False, "error": {"code": "E4004", "message": f"元素 {selector} 未找到: {e}"}}
    
    async def click(self, selector: str) -> dict:
        """点击元素。权限 L4。"""
        try:
            await self._page.click(selector)
            return {"success": True, "result": {"clicked": selector}}
        except Exception as e:
            return {"success": False, "error": {"code": "E4006", "message": str(e)}}
    
    async def fill(self, selector: str, text: str) -> dict:
        """在表单中输入文本。权限 L4。"""
        try:
            await self._page.fill(selector, text)
            return {"success": True, "result": {"filled": selector, "text": text}}
        except Exception as e:
            return {"success": False, "error": {"code": "E4006", "message": str(e)}}
    
    async def extract_content(self, selector: str = None) -> dict:
        """提取页面内容。权限 L1。"""
        try:
            if selector:
                text = await self._page.inner_text(selector)
            else:
                text = await self._page.inner_text("body")
            return {"success": True, "result": {"content": text, "length": len(text)}}
        except Exception as e:
            return {"success": False, "error": {"code": "E4006", "message": str(e)}}
    
    async def screenshot(self, full_page: bool = False) -> dict:
        """页面截图（用于 Vision 兜底）。"""
        try:
            import base64
            screenshot = await self._page.screenshot(full_page=full_page)
            return {
                "success": True,
                "result": {
                    "image_base64": base64.b64encode(screenshot).decode(),
                    "size_bytes": len(screenshot),
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "E4006", "message": str(e)}}
    
    async def close(self):
        """关闭浏览器连接。"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
```

---

## 5. Vision Engine (Ollama 兜底)

### 5.1 功能

| 功能 | 说明 | 超时 |
|------|------|------|
| describe | 描述屏幕内容（截图 -> 文本描述） | 30s |
| compare | 比较两张截图的差异 | 30s |
| ocr | OCR 文字识别 | 30s |

### 5.2 实现骨架

```python
# apps/runtime/src/engines/vision_engine.py

import logging
import base64
import httpx
from typing import Optional

logger = logging.getLogger("runtime.vision_engine")

VISION_MODEL = "qwen2.5vl:7b"  # 可配置
OLLAMA_VISION_URL = "http://localhost:11434"
VISION_TIMEOUT = 30  # 秒

class VisionEngine:
    """Ollama Vision 兜底引擎。"""
    
    def __init__(self, model: str = VISION_MODEL, base_url: str = OLLAMA_VISION_URL):
        self.model = model
        self.base_url = base_url
    
    async def describe(self, image_base64: str, prompt: str = "描述这个屏幕的内容") -> dict:
        """描述屏幕内容。"""
        return await self._call_vision(image_base64, prompt)
    
    async def ocr(self, image_base64: str) -> dict:
        """OCR 文字识别。"""
        return await self._call_vision(
            image_base64,
            "提取图片中的所有文字，只返回文字内容，不要其他描述。"
        )
    
    async def compare(self, image1_base64: str, image2_base64: str) -> dict:
        """比较两张截图的差异。"""
        # Ollama 多模态目前只支持单图，这里拼接描述
        desc1 = await self.describe(image1_base64, "描述这个屏幕")
        desc2 = await self.describe(image2_base64, "描述这个屏幕")
        
        # 简单文本对比
        return {
            "success": True,
            "result": {
                "image1_description": desc1.get("result", {}).get("description", ""),
                "image2_description": desc2.get("result", {}).get("description", ""),
                "changed": desc1.get("result", {}).get("description", "") != desc2.get("result", {}).get("description", ""),
            }
        }
    
    async def _call_vision(self, image_base64: str, prompt: str) -> dict:
        """调用 Ollama 视觉模型。"""
        try:
            async with httpx.AsyncClient(timeout=VISION_TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt,
                                "images": [image_base64],
                            }
                        ],
                        "stream": False,
                    }
                )
                
                if response.status_code != 200:
                    return {"success": False, "error": {"code": "E4007", "message": f"Ollama 返回 {response.status_code}"}}
                
                data = response.json()
                return {
                    "success": True,
                    "result": {
                        "description": data.get("message", {}).get("content", ""),
                        "model": self.model,
                    }
                }
        except httpx.TimeoutException:
            logger.warning(f"Vision 推理超时 ({VISION_TIMEOUT}s)")
            return {"success": False, "error": {"code": "E4008", "message": f"Vision 响应超时 ({VISION_TIMEOUT}s)"}}
        except Exception as e:
            return {"success": False, "error": {"code": "E4007", "message": str(e)}}
```

---

## 6. 三类基础 UI 操作验收

### 6.1 VSCode 操作（UIA）

```
目标: 在 VSCode 中打开文件
步骤:
  1. UIA 定位 VSCode 窗口
  2. UIA 点击菜单栏 "文件" -> "打开文件"
  3. UIA 在对话框中输入文件路径
  4. UIA 点击 "确定"
  5. 验证: 编辑器标签页显示文件名
```

### 6.2 Chrome 操作（CDP）

```
目标: 搜索技术文档并提取正文
步骤:
  1. CDP 导航到搜索引擎
  2. CDP 在搜索框中输入关键词
  3. CDP 点击搜索按钮
  4. 等待搜索结果
  5. CDP 点击第一个结果
  6. CDP 提取正文
  7. 验证: 正文长度 > 100 字符
```

### 6.3 混合操作（UIA + CDP + Vision 兜底）

```
目标: 页面元素无法通过 CSS 定位时的兜底
步骤:
  1. CDP 尝试 find_element -> 失败
  2. CDP screenshot()
  3. Vision describe() 识别元素位置
  4. CDP 通过坐标点击
  5. 验证: 页面跳转成功
```

---

## 7. 实现步骤

| 序号 | 任务 | 预计耗时 | 依赖 |
|------|------|---------|------|
| 1 | 实现 UIAEngine | 4h | M1 ProcessEngine |
| 2 | 实现 BrowserEngine（Playwright + CDP） | 4h | M1 AppScanner |
| 3 | 实现 VisionEngine（Ollama） | 2h | 无 |
| 4 | 编写 UIA MCP 工具 | 2h | 1 |
| 5 | 编写 Browser MCP 工具 | 2h | 2 |
| 6 | 编写 Vision MCP 工具 | 1h | 3 |
| 7 | 单元测试 | 3h | 1,2,3 |
| 8 | 三类 UI 操作集成测试 | 3h | 4,5,6 |
| 9 | 前端 UI 树可视化 | 3h | 1 |

---

## 8. 测试与验收标准

- [ ] UIA 可读取 VSCode 的 UI 树（深度 5 层）
- [ ] UIA 可定位并点击 VSCode 菜单元素
- [ ] BrowserEngine 可导航到 URL 并等待元素
- [ ] BrowserEngine 可提取页面正文
- [ ] VisionEngine 可在 30s 内返回截图描述
- [ ] Vision 超时后降级为其他方案（不阻断流程）
- [ ] 三类基础 UI 操作均可稳定执行
- [ ] 每次操作后 verify 通过

---

## 9. 交付物清单

| 交付物 | 路径 | 状态 |
|--------|------|------|
| UIAEngine | apps/runtime/src/engines/uia_engine.py | - |
| BrowserEngine | apps/runtime/src/engines/browser_engine.py | - |
| VisionEngine | apps/runtime/src/engines/vision_engine.py | - |
| UIA MCP 工具 | apps/runtime/src/mcp_tools/uia_*.py | - |
| Browser MCP 工具 | apps/runtime/src/mcp_tools/browser_*.py | - |
| Vision MCP 工具 | apps/runtime/src/mcp_tools/vision_*.py | - |
| 单元测试 | apps/runtime/tests/test_uia.py, test_browser.py, test_vision.py | - |

---

## 10. 风险与注意事项

| 风险 | 级别 | 应对 |
|------|------|------|
| UIA 在某些应用上不可用 | HIGH | 提前测试 VSCode/Chrome/File Explorer 的 UIA 可用性，如不可用则回退到 CDP/文件系统 |
| Playwright CDP 模式与 Chrome 版本不兼容 | MEDIUM | 锁定 Chrome 版本范围，或使用 Playwright 自带的 Chromium |
| Ollama Vision 模型加载慢（首次推理 10s+） | MEDIUM | 预热模型：启动时发送一次空请求 |
| 高分屏 UIA 坐标偏移 | LOW | M3 暂不使用坐标点击，M4 需要时再处理 |
| Chrome 多 profile 导致 CDP 连接失败 | LOW | 指定 Chrome user-data-dir |

---

## 11. 相关文档

- [../1-standards/00-project-overview.md](../1-standards/00-project-overview.md) - 全局规范
- [../2-milestones/03-m2-file-permission-audit.md](../2-milestones/03-m2-file-permission-audit.md) - 前置阶段
- [../2-milestones/05-m4-skill-workflow-executor.md](../2-milestones/05-m4-skill-workflow-executor.md) - 下一阶段
