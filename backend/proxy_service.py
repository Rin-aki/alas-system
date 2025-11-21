# -*- coding: utf-8 -*-
# 反向代理服务 - 修复WebSocket数据库连接问题
import asyncio
import websockets
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, Request, Depends
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from jose import JWTError, jwt
import httpx
import logging
from urllib.parse import urlencode
from contextlib import asynccontextmanager
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="反向代理服务", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DATABASE_URL = "mysql+pymysql://guojiang:lpfH5a3h78@MySQL/DataBase"
engine = create_engine(
    DATABASE_URL,
    pool_size=10,              # 🔥 从10增加到50
    max_overflow=20,           # 🔥 从20增加到50，总共100个连接
    pool_recycle=1800,         # 🔥 30分钟回收（从3600减少）
    pool_timeout=10,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SECRET_KEY = "lpfH5a3h78"
ALGORITHM = "HS256"

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    has_purchased = Column(Boolean, default=False)
    purchase_expires = Column(DateTime, nullable=True)
    alas_port = Column(Integer, nullable=True)
    blhx_port = Column(Integer, nullable=True)
    ws_port = Column(Integer, nullable=True)
    server_ip = Column(Integer, nullable=True)

Base.metadata.create_all(bind=engine)

def get_db():
    """数据库依赖注入，确保会话正确关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def get_db_context():
    """异步上下文管理器，用于需要独立数据库会话的场景"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ 关键修复2: 增加缓存时间，减少数据库查询
user_cache = {}

async def get_current_user_from_token(access_token: str) -> Optional[dict]:
    """从token获取用户信息，带缓存优化"""
    if not access_token:
        return None
    
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
            
        cache_key = f"user_{user_id}"
        if cache_key in user_cache:
            cached_user, cache_time = user_cache[cache_key]
            # ✅ 缓存时间从5分钟增加到15分钟，减少数据库查询
            if (datetime.utcnow() - cache_time).seconds < 900:  # 15分钟
                logger.debug(f"使用缓存的用户信息: {user_id}")
                return cached_user
        
        # ✅ 关键修复3: 使用上下文管理器，确保立即释放连接
        async with get_db_context() as db:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user_data = {
                    "id": user.id,
                    "email": user.email,
                    "is_active": user.is_active,
                    "has_purchased": user.has_purchased,
                    "alas_port": user.alas_port,
                    "blhx_port": user.blhx_port,
                    "ws_port": user.ws_port,
                    "server_ip": user.server_ip
                }
                user_cache[cache_key] = (user_data, datetime.utcnow())
                logger.info(f"从数据库加载用户信息并缓存: {user_id}")
                return user_data
    except JWTError as e:
        logger.warning(f"JWT验证失败: {e}")
    except Exception as e:
        logger.error(f"获取用户信息时出错: {e}")
    
    return None

# ✅ 关键修复4: WebSocket代理中不持有数据库连接
@app.websocket("/")
async def proxy_ws(websocket: WebSocket):
    """WebSocket代理，完全不持有数据库连接"""
    await websocket.accept()
    closed = False

    try:
        # 🔥 关键：验证后立即释放数据库连接，不在整个WebSocket生命周期持有
        cookie_header = websocket.headers.get("cookie", "")
        cookies = {kv.split("=")[0]: kv.split("=")[1] for kv in cookie_header.split("; ") if "=" in kv}
        token = cookies.get("access_token")

        if not token:
            logger.warning("WebSocket认证失败 - 缺少令牌")
            closed = True
            await websocket.close()
            return

        # 使用缓存获取用户信息，避免长时间持有数据库连接
        user_data = await get_current_user_from_token(token)
        if not user_data:
            logger.warning("WebSocket认证失败 - 无效令牌")
            closed = True
            await websocket.close()
            return

        # 🔥 此时数据库连接已经释放，user_data是内存中的字典
        logger.info(f"WebSocket代理开始 - 用户: {user_data['email']}")

        # 确定目标服务
        host = websocket.headers.get("host", "")
        query_params = websocket.query_params
        query_string = urlencode(query_params)

        if "scrcpy" in host:
            use_bytes = True
            target_ws_url = f"ws://10.10.10.{user_data['server_ip']}:{user_data['ws_port']}/?{query_string}"
            logger.info(f"代理到scrcpy: {target_ws_url}")
        elif "alas" in host:
            use_bytes = False
            target_ws_url = f"ws://10.10.10.{user_data['server_ip']}:{user_data['alas_port']}/?{query_string}"
            logger.info(f"代理到alas: {target_ws_url}")
        else:
            logger.warning(f"未知的服务域名: {host}")
            closed = True
            await websocket.close()
            return

        # 构建额外头部
        additional_headers = {
            "User-Agent": websocket.headers.get("user-agent", ""),
            "X-Forwarded-For": websocket.client.host if websocket.client else "unknown",
            "X-Forwarded-Host": host,
            "X-Real-IP": websocket.client.host if websocket.client else "unknown"
        }

        # 建立代理连接
        async with websockets.connect(target_ws_url, additional_headers=additional_headers) as remote_ws:
            logger.info(f"WebSocket代理连接建立成功 - 用户: {user_data['email']}")

            async def client_to_server():
                try:
                    while True:
                        if use_bytes:
                            data = await websocket.receive_bytes()
                            await remote_ws.send(data)
                        else:
                            msg = await websocket.receive_text()
                            await remote_ws.send(msg)
                except Exception as e:
                    logger.debug(f"[client_to_server] 连接关闭: {e}")

            async def server_to_client():
                try:
                    while True:
                        msg = await remote_ws.recv()
                        if use_bytes:
                            await websocket.send_bytes(msg)
                        else:
                            await websocket.send_text(msg)
                except Exception as e:
                    logger.debug(f"[server_to_client] 连接关闭: {e}")

            await asyncio.gather(client_to_server(), server_to_client())
            logger.info(f"WebSocket代理正常关闭 - 用户: {user_data['email']}")

    except websockets.exceptions.WebSocketException as e:
        logger.error(f"WebSocket异常: {e}")
    except Exception as e:
        logger.error(f"WebSocket连接失败: {e}", exc_info=True)
    finally:
        if not closed:
            try:
                await websocket.close()
            except RuntimeError:
                pass

# HTTP客户端配置
http_client = httpx.AsyncClient(
    timeout=30.0,
    limits=httpx.Limits(
        max_keepalive_connections=50,
        max_connections=100,
        keepalive_expiry=30.0
    ),
    http2=False
)

EXCLUDED_RESPONSE_HEADERS = {
    "content-length",
    "transfer-encoding", 
    "content-encoding",
    "connection",
    "upgrade",
    "proxy-authenticate",
    "proxy-authorization"
}
EXCLUDED_REQUEST_HEADERS = {
    "host",
    "connection",
    "content-length",
    "upgrade",
    "proxy-connection"
}

def prepare_proxy_headers(request: Request) -> dict:
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in EXCLUDED_REQUEST_HEADERS
    }
    
    client_ip = request.client.host if request.client else "unknown"
    original_host = request.headers.get("host", "")
    scheme = request.url.scheme
    port = request.url.port or (443 if scheme == "https" else 80)
    
    forward_headers.update({
        "X-Forwarded-For": request.headers.get("x-forwarded-for", client_ip),
        "X-Forwarded-Host": request.headers.get("x-forwarded-host", original_host),
        "X-Forwarded-Proto": request.headers.get("x-forwarded-proto", scheme),
        "X-Forwarded-Port": request.headers.get("x-forwarded-port", str(port)),
        "X-Real-IP": request.headers.get("x-real-ip", client_ip),
        "X-Real-Proto": scheme,
        "X-Original-Host": original_host
    })
    
    return forward_headers

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_http(path: str, request: Request):
    """HTTP请求代理"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(status_code=401, detail="缺少访问令牌")
        
        # ✅ 使用缓存获取用户信息，立即释放数据库连接
        user_data = await get_current_user_from_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="无效的访问令牌")
        
        host = request.headers.get("host", "")
        if "scrcpy" in host:
            target_url = f"http://10.10.10.{user_data['server_ip']}:{user_data['ws_port']}/{path}"
            target_host = f"10.10.10.{user_data['server_ip']}:{user_data['ws_port']}"
        elif "alas" in host:
            target_url = f"http://10.10.10.{user_data['server_ip']}:{user_data['alas_port']}/{path}"
            target_host = f"10.10.10.{user_data['server_ip']}:{user_data['alas_port']}"
        else:
            raise HTTPException(status_code=404, detail="未知的服务域名")
        
        logger.info(f"代理请求: {request.method} {request.url} -> {target_url}")
        
        forward_headers = prepare_proxy_headers(request)
        forward_headers["Host"] = target_host
        
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
        
        try:
            async with http_client.stream(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body,
                params=dict(request.query_params)
            ) as proxied_response:
                content_chunks = []
                async for chunk in proxied_response.aiter_bytes():
                    content_chunks.append(chunk)
                content = b"".join(content_chunks)
                
                response_headers = {
                    k: v for k, v in proxied_response.headers.items()
                    if k.lower() not in EXCLUDED_RESPONSE_HEADERS
                }
                
                if "access-control-allow-origin" not in [h.lower() for h in response_headers.keys()]:
                    origin = request.headers.get("origin")
                    if origin:
                        response_headers["Access-Control-Allow-Origin"] = origin
                        response_headers["Access-Control-Allow-Credentials"] = "true"
                
                return Response(
                    content=content,
                    status_code=proxied_response.status_code,
                    headers=response_headers,
                    media_type=proxied_response.headers.get("content-type")
                )
                
        except httpx.TimeoutException:
            logger.error(f"代理超时: {target_url}")
            raise HTTPException(status_code=504, detail="网关超时")
        except httpx.ConnectError:
            logger.error(f"连接失败: {target_url}")
            raise HTTPException(status_code=502, detail="服务不可用")
        except httpx.RequestError as e:
            logger.error(f"代理请求失败 {target_url}: {str(e)}")
            raise HTTPException(status_code=502, detail="网关错误")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"代理过程中发生未预期错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")



@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    logger.info("正在关闭HTTP客户端...")
    await http_client.aclose()
    logger.info("正在清理用户缓存...")
    user_cache.clear()
    logger.info("资源清理完成")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6300, log_level="info")
