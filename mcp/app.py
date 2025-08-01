from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime

app = FastAPI(title="Campus Assistant MCP API")

class Command(BaseModel):
    command: str
    user_id: str
    role: str
    timestamp: datetime
    context: dict

@app.post("/mcp/command")
async def handle_mcp(cmd: Command):
    # TODO: 按 cmd.command 路由到不同处理函数
    return {"status": "ok", "echo": cmd.dict()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
