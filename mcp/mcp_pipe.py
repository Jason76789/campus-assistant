"""
MCP pipe: connect to remote MCP broker (WebSocket) and pipe JSON-RPC
messages between broker and a local MCP script process.

Usage:
  Set environment variable MCP_ENDPOINT to wss://... broker endpoint
  Then run:
    python mcp_pipe.py <mcp_script>

Example:
  $env:MCP_ENDPOINT="wss://api.xiaozhi.me/mcp/?token=..."
  python mcp_pipe.py mcp/student_tools.py
"""
import asyncio
import websockets
import subprocess
import logging
import os
import signal
import sys
import random
from dotenv import load_dotenv

load_dotenv()

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MCP_PIPE")

# Reconnection/backoff params
INITIAL_BACKOFF = 1
MAX_BACKOFF = 600
reconnect_attempt = 0
backoff = INITIAL_BACKOFF


async def connect_with_retry(uri, mcp_script):
    global reconnect_attempt, backoff
    while True:
        try:
            if reconnect_attempt > 0:
                wait_time = backoff * (1 + random.random() * 0.1)
                logger.info(f"Waiting {wait_time:.2f}s before reconnection attempt {reconnect_attempt}...")
                await asyncio.sleep(wait_time)
            await connect_to_server(uri, mcp_script)
        except Exception as e:
            reconnect_attempt += 1
            logger.warning(f"Connection closed (attempt: {reconnect_attempt}): {e}")
            backoff = min(backoff * 2, MAX_BACKOFF)


async def connect_to_server(uri, mcp_script):
    global reconnect_attempt, backoff
    try:
        logger.info("Connecting to WebSocket server...")
        async with websockets.connect(uri) as websocket:
            logger.info("Successfully connected to WebSocket server")
            reconnect_attempt = 0
            backoff = INITIAL_BACKOFF

            # Start the child process (mcp script)
            # Use sys.executable to ensure we use the same Python interpreter (venv)
            process = subprocess.Popen(
                [sys.executable, mcp_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,  # text mode
                encoding='utf-8'
            )
            logger.info(f"Started {mcp_script} process (pid={process.pid})")

            # Run pipes concurrently
            await asyncio.gather(
                pipe_websocket_to_process(websocket, process),
                pipe_process_to_websocket(process, websocket),
                pipe_process_stderr_to_terminal(process)
            )
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"WebSocket connection closed: {e}")
        raise
    except Exception as e:
        logger.error(f"Connection error: {e}")
        raise
    finally:
        if 'process' in locals():
            try:
                logger.info(f"Terminating {mcp_script} process")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            logger.info(f"{mcp_script} process terminated")


async def pipe_websocket_to_process(websocket, process):
    """Read data from WebSocket and write to process stdin"""
    try:
        while True:
            # Read message from WebSocket
            message = await websocket.recv()
            logger.debug(f"<< {message[:120]}...")

            # Write to process stdin (in text mode)
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            process.stdin.write(message + '\n')
            process.stdin.flush()
    except Exception as e:
        logger.error(f"Error in WebSocket to process pipe: {e}")
        raise
    finally:
        # Close process stdin
        if not process.stdin.closed:
            process.stdin.close()


async def pipe_process_to_websocket(process, websocket):
    """Read data from process stdout and send to WebSocket"""
    try:
        while True:
            # Read data from process stdout
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, process.stdout.readline)

            if not data:
                logger.info("Process has ended output")
                break

            # Send data to WebSocket
            logger.debug(f">> {data[:120]}...")
            # In text mode, data is already a string
            await websocket.send(data)
    except Exception as e:
        logger.error(f"Error in process to WebSocket pipe: {e}")
        raise


async def pipe_process_stderr_to_terminal(process):
    """Read data from process stderr and print to terminal"""
    try:
        loop = asyncio.get_event_loop()
        while True:
            data = await loop.run_in_executor(None, process.stderr.readline)
            if not data:
                logger.info("Process has ended stderr output")
                break
            sys.stderr.write(data)
            sys.stderr.flush()
    except Exception as e:
        logger.error(f"Error in process stderr pipe: {e}")
        raise


def signal_handler(sig, frame):
    logger.info("Received interrupt signal, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    if len(sys.argv) < 2:
        logger.error("Usage: mcp_pipe.py <mcp_script>")
        sys.exit(1)

    mcp_script = sys.argv[1]
    endpoint_url = os.environ.get("MCP_ENDPOINT")
    if not endpoint_url:
        logger.error("Please set MCP_ENDPOINT environment variable")
        sys.exit(1)

    logger.info("Starting MCP pipe. endpoint=%s, script=%s", endpoint_url, mcp_script)
    try:
        asyncio.run(connect_with_retry(endpoint_url, mcp_script))
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.exception("Program execution error: %s", e)
