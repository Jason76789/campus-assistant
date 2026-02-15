# student_tools.py
import os
import sys
import logging
import json
import requests
from typing import Dict, Any, Optional
from datetime import date, datetime
from zoneinfo import ZoneInfo
import uuid

# ----------------- robust import fallback for "mcp" package -----------------
# Try normal import first; if it fails, try to adjust sys.path so package can be found.
try:
    from mcp.server.fastmcp import FastMCP
except Exception:
    # add parent directory of this file to sys.path (covers running inside package dir)
    this_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(this_dir, ".."))  # parent of current dir
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        # final fallback: try importing server.fastmcp if package root is current dir
        try:
            from server.fastmcp import FastMCP
        except Exception as e:
            # re-raise with clearer error to appear in stderr logs
            raise ImportError("Cannot import FastMCP from 'mcp.server.fastmcp' or 'server.fastmcp'. "
                              "Check PYTHONPATH and package layout.") from e

# ----------------- configuration -----------------
# Prefer environment variable (mcp_pipe will load .env and pass it through)
BASE_URL = os.environ.get("MCP_BASE_URL") or os.environ.get("BASE_URL") or "http://127.0.0.1:8000"
# Optional auth token
AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN") or os.environ.get("MCP_AUTH") or None

# timezone for timestamps
TZ = ZoneInfo("Asia/Shanghai")

# logging -> stderr (do NOT use print())
logger = logging.getLogger("StudentTools")
if not logger.handlers:
    h = logging.StreamHandler()  # defaults to stderr
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)

# MCP instance
mcp = FastMCP("StudentCampusAssistant")

# ----------------- helpers -----------------
def _now_iso_sh() -> str:
    return datetime.now(TZ).isoformat()

def _make_request(method: str, endpoint: str, params: dict | None = None, json_body: dict | None = None) -> Dict[str, Any]:
    """Unified HTTP helper — logs to stderr, returns dict (never prints)."""
    url = BASE_URL.rstrip("/") + endpoint
    headers = {"Accept": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    try:
        resp = requests.request(method, url, params=params, json=json_body, headers=headers, timeout=10)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"status": "error", "detail": "non-json response", "raw": resp.text}
    except requests.exceptions.RequestException as e:
        logger.error("HTTP error %s %s -> %s", method, url, str(e))
        return {"status": "error", "detail": str(e)}

# ----------------- MCP tools -----------------
@mcp.tool()
def get_grades(student_external_id: str, requester_external_id: str) -> Dict[str, Any]:
    logger.info("get_grades student=%s requester=%s", student_external_id, requester_external_id)
    endpoint = f"/mcp/grades/student/{student_external_id}"
    params = {"requester_id": requester_external_id}
    return _make_request("GET", endpoint, params=params)

@mcp.tool()
def get_today_memos(student_external_id: str) -> Dict[str, Any]:
    logger.info("get_today_memos student=%s", student_external_id)
    command = {
        "command": "get_today_memo",
        "user_id": str(student_external_id),
        "role": "student",
        "timestamp": _now_iso_sh(),
        "context": {}
    }
    return _make_request("POST", "/mcp/command", json_body=command)

@mcp.tool()
def add_memo(student_external_id: str, content: str, remind_date: Optional[str] = None) -> Dict[str, Any]:
    logger.info("add_memo student=%s content=%s", student_external_id, content)
    if remind_date is None:
        remind_date = date.today().isoformat()
    command = {
        "command": "add_memo",
        "user_id": str(student_external_id),
        "role": "student",
        "timestamp": _now_iso_sh(),
        "context": {
            "content": content,
            "remind_date": remind_date
        },
        "idempotency_key": str(uuid.uuid4())  # help backend dedupe
    }
    return _make_request("POST", "/mcp/command", json_body=command)

@mcp.tool()
def send_message(sender_external_id: str, receiver_external_id: str, content: str) -> Dict[str, Any]:
    logger.info("send_message sender=%s receiver=%s", sender_external_id, receiver_external_id)
    command = {
        "command": "leave_message",
        "user_id": str(sender_external_id),
        "role": "student",
        "timestamp": _now_iso_sh(),
        "context": {
            "receiver_id": receiver_external_id,
            "content": content,
            "priority": "normal"
        },
        "idempotency_key": str(uuid.uuid4())
    }
    return _make_request("POST", "/mcp/command", json_body=command)

@mcp.tool()
def get_messages(user_external_id: str) -> Dict[str, Any]:
    logger.info("get_messages user=%s", user_external_id)
    command = {
        "command": "get_messages",
        "user_id": str(user_external_id),
        "role": "student",
        "timestamp": _now_iso_sh(),
        "context": {}
    }
    return _make_request("POST", "/mcp/command", json_body=command)

@mcp.tool()
def poll_new_items(user_external_id: str, timeout_seconds: int = 5) -> Dict[str, Any]:
    logger.info("poll_new_items user=%s timeout=%s", user_external_id, timeout_seconds)
    # If backend exposes /mcp/user/<ident> to translate external->internal id:
    user_info = _make_request("GET", f"/mcp/user/{user_external_id}")
    if user_info.get("status") != "success" or not user_info.get("user"):
        return {"status": "error", "detail": "cannot resolve user", "items": []}
    internal_id = user_info["user"].get("id")
    if not internal_id:
        return {"status": "error", "detail": "no internal id", "items": []}
    # Call poll endpoint directly
    return _make_request("GET", "/mcp/poll", params={"user_id": internal_id, "timeout": timeout_seconds})

# ----------------- run -----------------
if __name__ == "__main__":
    logger.info("StudentTools starting up. Backend=%s", BASE_URL)
    # do not print anything else to stdout
    mcp.run(transport="stdio")
