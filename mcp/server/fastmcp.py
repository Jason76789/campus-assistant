import logging
import sys
import json

logger = logging.getLogger('FastMCP')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class FastMCP:
    def __init__(self, name: str):
        self.name = name
        self.tools = {}
        logger.info(f"FastMCP instance '{self.name}' initialized.")

    def tool(self):
        def decorator(func):
            tool_name = func.__name__
            self.tools[tool_name] = func
            logger.info(f"Registered tool: {tool_name}")
            return func
        return decorator

    def run(self, transport: str = "stdio"):
        logger.info(f"FastMCP '{self.name}' running with transport: {transport}")
        if transport == "stdio":
            self._run_stdio()
        else:
            logger.error(f"Unsupported transport: {transport}")

    def _run_stdio(self):
        logger.info("Starting stdio transport loop...")
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                request = json.loads(line)
                tool_name = request.get("tool_name")
                tool_args = request.get("arguments", {})

                if tool_name in self.tools:
                    logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
                    result = self.tools[tool_name](**tool_args)
                    sys.stdout.write(json.dumps({"status": "success", "result": result}) + '\n')
                else:
                    error_msg = f"Tool '{tool_name}' not found."
                    logger.error(error_msg)
                    sys.stdout.write(json.dumps({"status": "error", "reason": error_msg}) + '\n')
                sys.stdout.flush()
            except json.JSONDecodeError:
                error_msg = "Invalid JSON input."
                logger.error(error_msg)
                sys.stdout.write(json.dumps({"status": "error", "reason": error_msg}) + '\n')
                sys.stdout.flush()
            except Exception as e:
                error_msg = f"Error executing tool: {e}"
                logger.error(error_msg)
                sys.stdout.write(json.dumps({"status": "error", "reason": error_msg}) + '\n')
                sys.stdout.flush()
