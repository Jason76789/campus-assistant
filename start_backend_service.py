#!/usr/bin/env python3
"""
Windows 服务环境下启动后端服务的 Python 脚本
解决批处理文件在服务环境下无法正常运行的问题
"""
import os
import sys
import subprocess
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backend_service.log'),
        logging.StreamHandler()
    ]
)

def main():
    logging.info("Starting backend service...")
    
    # 设置工作目录
    os.chdir("d:\\python\\campus-assistant")
    
    # 启动 uvicorn 服务器
    cmd = [
        sys.executable,  # 使用当前 Python 解释器
        "-m", "uvicorn", 
        "mcp.app:app", 
        "--host", "0.0.0.0", 
        "--port", "8000"
    ]
    
    try:
        logging.info(f"Executing command: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 实时输出日志
        for line in process.stdout:
            logging.info(line.strip())
            
        # 等待进程结束
        process.wait()
        
    except Exception as e:
        logging.error(f"Failed to start backend service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
