# apps/gateway/main.py
import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import grpc

# ---- 路径修正：让生成的 inference_pb2*.py 能用它的顶层导入 ----
# 生成器在 inference_pb2_grpc.py 中写的是 "import inference_pb2"
# 所以需要把当前目录加入 sys.path，便于找到同目录的文件。
CURRENT_DIR = os.path.dirname(__file__)
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

# ---- gRPC 生成文件导入 ----
import inference_pb2 as inference__pb2
import inference_pb2_grpc as inference__pb2_grpc

# ---- 配置：推理服务地址可通过环境变量设置 ----
INFER_HOST = os.getenv("INFER_HOST", "localhost")
INFER_PORT = os.getenv("INFER_PORT", "50051")
INFER_TARGET = f"{INFER_HOST}:{INFER_PORT}"

app = FastAPI(title="LLM HighPerf Gateway", version="0.1.0")


# ---- 定义http请求体的数据模型 ----
class GenerateRequestBody(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 128

# ---- 日志配置和健康检查代码 ----
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

# ---- 健康检查 ----
@app.get("/health")
def health():
    logger.info(f"Health check. Infer target: {INFER_HOST}:{INFER_PORT}")
    return {"ok": True, "infer_target": f"{INFER_HOST}:{INFER_PORT}"}


# ---- 生成接口：调用 C++ gRPC 推理服务 ----
@app.post("/generate")
def generate(req: GenerateRequestBody):
    try:
        # 与后端的 C++ gRPC 服务建立一个不安全的连接
        with grpc.insecure_channel(INFER_TARGET) as channel:
            # 创建一个客户端存根 (Stub)，这是与服务器对话的入口
            stub = inference__pb2_grpc.InferenceServiceStub(channel)
            # 调用 gRPC 方法
            # 调用存根的 Generate 方法，就像调用一个本地函数
            # 使用 inference__pb2.GenerateRequest 创建请求数据
            # 发送人：HTTP 请求的内容，接收方：后端C++服务器， 数据结构：proto
            resp = stub.Generate(
                inference__pb2.GenerateRequest(
                    prompt=req.prompt,
                    max_tokens=req.max_tokens or 128,
                )
            )
    except grpc.RpcError as e:
        # 常见错误：C++ 服务未启动、目标不可达等
        status_code = 502  # Bad Gateway
        detail = f"gRPC call failed: {e.code().name} - {e.details()}"
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gateway error: {e}")

    # 返回 gRPC 响应中的生成文本，以 JSON 格式返回给 HTTP 客户端
    return {"text": resp.text}


# ---- 给根路径 / 加一个欢迎页 ----
@app.get("/")
def root():
    return {"message": "LLM HighPerf Gateway is running", "docs": "/docs", "health": "/health"}

# ---- Mock 生成接口：用于测试和调试 ----
@app.post("/generate_mock")
def generate_mock(req: GenerateRequestBody):
    return {
        "text": f"[MOCK] Prompt: {req.prompt[:40]}... (max_tokens={req.max_tokens or 128})"
    }

