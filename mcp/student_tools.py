# mcp/student_tools.py
from mcp.server.fastmcp import FastMCP
import requests
import json
import logging
from typing import Dict, Any, Optional
from datetime import date

# --- 配置 ---
# FastAPI 后端应用的地址
BASE_URL = "http://127.0.0.1:8000"
logger = logging.getLogger('StudentTools')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- MCP 服务定义 ---
mcp = FastMCP("StudentCampusAssistant")

# --- 辅助函数 ---
def _make_request(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """一个通用的请求辅助函数"""
    url = f"{BASE_URL}{endpoint}"
    try:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()  # 如果状态码不是 2xx，则抛出异常
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {method.upper()} {url} - {e}")
        # 返回一个标准的错误格式
        return {"status": "error", "detail": str(e)}

# --- MCP 工具定义 ---

@mcp.tool()
def get_grades(student_external_id: str, requester_external_id: str) -> Dict[str, Any]:
    """
    查询指定学生的成绩。
    需要提供请求者(requester)的 external_id 以进行权限验证。
    请求者可以是学生本人、其家长或老师。
    """
    logger.info(f"工具: get_grades, 学生ID: {student_external_id}, 请求者ID: {requester_external_id}")
    endpoint = f"/mcp/grades/student/{student_external_id}"
    params = {"requester_id": requester_external_id}
    return _make_request("GET", endpoint, params=params)

@mcp.tool()
def get_today_memos(student_external_id: str) -> Dict[str, Any]:
    """获取指定学生今天的备忘录。"""
    logger.info(f"工具: get_today_memos, 学生ID: {student_external_id}")
    command = {
        "command": "get_today_memo",
        "user_id": student_external_id,
        "role": "student", # 假设调用者是学生
        "timestamp": "2025-10-25T12:00:00Z", # 时间戳可以是任意有效值
        "context": {}
    }
    return _make_request("POST", "/mcp/command", json=command)

@mcp.tool()
def add_memo(student_external_id: str, content: str, remind_date: Optional[str] = None) -> Dict[str, Any]:
    """
    为指定学生添加一条备忘录。
    remind_date 是一个可选的 YYYY-MM-DD 格式的字符串，如果未提供，则默认为今天。
    """
    logger.info(f"工具: add_memo, 学生ID: {student_external_id}, 内容: {content}")
    if remind_date is None:
        remind_date = date.today().isoformat()

    command = {
        "command": "add_memo",
        "user_id": student_external_id,
        "role": "student",
        "timestamp": "2025-10-25T12:00:00Z",
        "context": {
            "content": content,
            "remind_date": remind_date
        }
    }
    return _make_request("POST", "/mcp/command", json=command)

@mcp.tool()
def send_message(sender_external_id: str, receiver_external_id: str, content: str) -> Dict[str, Any]:
    """从一个用户发送消息给另一个用户。"""
    logger.info(f"工具: send_message, 发送者: {sender_external_id}, 接收者: {receiver_external_id}")
    command = {
        "command": "leave_message",
        "user_id": sender_external_id,
        "role": "student", # 假设角色，后端可能会根据ID重新判断
        "timestamp": "2025-10-25T12:00:00Z",
        "context": {
            "receiver_id": receiver_external_id,
            "content": content,
            "priority": "normal"
        }
    }
    return _make_request("POST", "/mcp/command", json=command)

@mcp.tool()
def get_messages(user_external_id: str) -> Dict[str, Any]:
    """获取指定用户收到的所有消息。"""
    logger.info(f"工具: get_messages, 用户ID: {user_external_id}")
    command = {
        "command": "get_messages",
        "user_id": user_external_id,
        "role": "student",
        "timestamp": "2025-10-25T12:00:00Z",
        "context": {}
    }
    return _make_request("POST", "/mcp/command", json=command)

@mcp.tool()
def poll_new_items(user_external_id: str) -> Dict[str, Any]:
    """
    为指定用户轮询新的待办事项，例如新消息、通知、提醒等。
    这是一个长轮询接口，可能会等待几秒钟直到有新项目或超时。
    """
    logger.info(f"工具: poll_new_items, 用户ID: {user_external_id}")
    # 注意：FastAPI 后端使用的是 internal user_id，这里需要转换。
    # 为了简化，我们首先需要一个方法从 external_id 获取 internal_id。
    # 假设有一个这样的端点 /mcp/user/{user_identifier}
    user_info_resp = _make_request("GET", f"/mcp/user/{user_external_id}")
    if user_info_resp.get("status") != "success" or not user_info_resp.get("user"):
        return {"status": "error", "detail": "无法获取用户信息", "items": []}
    
    internal_user_id = user_info_resp["user"].get("id")
    if not internal_user_id:
        return {"status": "error", "detail": "无法解析用户的内部ID", "items": []}

    endpoint = f"/mcp/poll"
    params = {"user_id": internal_user_id, "timeout": 5} # 5秒超时
    return _make_request("GET", endpoint, params=params)


# --- 启动服务 ---
if __name__ == "__main__":
    logger.info("学生助手 MCP 工具服务启动...")
    logger.info(f"将连接到后端 API: {BASE_URL}")
    mcp.run(transport="stdio")
