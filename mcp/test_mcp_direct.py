#!/usr/bin/env python3
"""
Direct test script for student_tools.py MCP tools.
This runs student_tools.py in stdio mode and sends test JSON-RPC requests.
"""
import subprocess
import json
import sys
import time

def send_request(process, request):
    """Send a JSON-RPC request and wait for response"""
    request_str = json.dumps(request, separators=(",", ":"), ensure_ascii=False) + "\n"
    process.stdin.write(request_str)
    process.stdin.flush()

    # Wait for response (with timeout)
    response = None
    start = time.time()
    timeout = 10

    while time.time() - start < timeout:
        try:
            line = process.stdout.readline()
            if line:
                try:
                    response = json.loads(line.rstrip())
                    break
                except json.JSONDecodeError:
                    continue
        except:
            break

    return response

def main():
    print("Starting student_tools.py in stdio mode...")
    process = subprocess.Popen(
        [sys.executable, 'student_tools.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8'
    )

    # Test 1: MCP Initialize
    print("\n[Test 1] Sending initialize request...")
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test_client",
                "version": "1.0.0"
            }
        }
    }
    init_resp = send_request(process, init_req)
    print(f"Initialize response: {json.dumps(init_resp, indent=2, ensure_ascii=False)}")

    # Test 2: Send initialized notification
    print("\n[Test 2] Sending initialized notification...")
    initialized_notif = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
    process.stdin.write(json.dumps(initialized_notif) + "\n")
    process.stdin.flush()

    # Test 3: Get tools list
    print("\n[Test 3] Requesting tools/list...")
    tools_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list"
    }
    tools_resp = send_request(process, tools_req)
    print(f"Tools list response: {json.dumps(tools_resp, indent=2, ensure_ascii=False)}")

    # Test 4: Test a simple tool call (get_messages with empty user)
    print("\n[Test 4] Testing get_messages tool...")
    tool_call_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_messages",
            "arguments": {
                "user_external_id": "test_user"
            }
        }
    }
    tool_resp = send_request(process, tool_call_req)
    print(f"Tool call response: {json.dumps(tool_resp, indent=2, ensure_ascii=False)}")

    # Clean up
    print("\nCleaning up...")
    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

    print("\n=== Test Summary ===")
    print("If all tests above show responses, MCP tools are working correctly.")
    print("If you see timeouts or no responses, check:")
    print("1. FastAPI backend is running at http://127.0.0.1:8000")
    print("2. student_tools.py can connect to the backend")
    print("3. Environment variables are set correctly (MCP_BASE_URL)")

if __name__ == "__main__":
    main()
