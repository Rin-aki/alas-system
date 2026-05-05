# -*- coding: utf-8 -*-
# 反向代理服务 - 修复WebSocket数据库连接问题
import asyncio
import base64
import websockets
from pathlib import Path
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
from typing import Optional, cast

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


import os
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://guojiang:lpfH5a3h78@10.10.10.1:3306/DataBase")
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

SECRET_KEY = os.getenv("USER_JWT_SECRET", "lpfH5a3h78")
ALGORITHMS = ["HS256", "HS384", "HS512"]

def resolve_jwt_signing_key(secret: str) -> bytes:
    """Mirror the Spring Boot JwtService key derivation so tokens validate consistently."""
    try:
        decoded = base64.b64decode(secret, validate=True)
        if len(decoded) >= 48:
            return decoded
    except Exception:
        pass

    raw = secret.encode("utf-8")
    key = bytearray(48)
    for index in range(48):
        key[index] = raw[index % len(raw)]
    return bytes(key)

JWT_SIGNING_KEY = resolve_jwt_signing_key(SECRET_KEY)

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    has_purchased = Column(Boolean, default=False)
    purchase_expires = Column(DateTime, nullable=True)
    alas_ip = Column(Integer, nullable=True)
    blhx_ip = Column(Integer, nullable=True)
    ws_ip = Column(Integer, nullable=True)

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

def split_service_path(raw_path: str) -> tuple[Optional[str], str]:
    normalized = raw_path.strip("/")
    if not normalized:
        return None, ""

    first_segment, _, remainder = normalized.partition("/")
    if first_segment in {"scrcpy", "alas"}:
        return first_segment, remainder

    return None, normalized


async def get_current_user_from_token(access_token: str) -> Optional[dict]:
    """从token获取用户信息，带缓存优化"""
    if not access_token:
        return None
    
    try:
        payload = jwt.decode(access_token, JWT_SIGNING_KEY, algorithms=ALGORITHMS)
        user_id: str = payload.get("sub")
        if not user_id:
            return None
            
        cache_key = f"user_{user_id}"
        if cache_key in user_cache:
            cached_user, cache_time = user_cache[cache_key]
            # ✅ 缓存时间从5分钟增加到15分钟，减少数据库查询
            if (datetime.now() - cache_time).seconds < 900:  # 15分钟
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
                    "purchase_expires": user.purchase_expires,
                    "alas_ip": user.alas_ip,
                    "blhx_ip": user.blhx_ip,
                    "ws_ip": user.ws_ip
                }
                user_cache[cache_key] = (user_data, datetime.now())
                logger.info(f"从数据库加载用户信息并缓存: {user_id}")
                return user_data
    except JWTError as e:
        logger.warning(f"JWT验证失败: {e}")
    except Exception as e:
        logger.error(f"获取用户信息时出错: {e}")
    
    return None

async def ensure_purchase_valid(user_id: int) -> bool:
    """
    确保用户的购买状态未过期（优先使用缓存）。
    - 返回 True 表示可以继续访问
    - 返回 False 表示未购买或已过期（并会在过期时自动更新数据库状态）
    """
    try:
        # ✅ 优化：先检查缓存中的购买状态
        cache_key = f"user_{user_id}"
        if cache_key in user_cache:
            cached_user, cache_time = user_cache[cache_key]

            # 如果缓存未过期（15分钟内），优先使用缓存检查
            if (datetime.now() - cache_time).seconds < 900:
                # 未购买直接拒绝
                if not cached_user.get("has_purchased"):
                    return False

                # 检查过期时间
                expires_str = cached_user.get("purchase_expires")
                if not expires_str:
                    # 没有过期时间，需要更新数据库
                    async with get_db_context() as db:
                        user = db.query(User).filter(User.id == int(user_id)).first()
                        if user:
                            user.has_purchased = False  # type: ignore[assignment]
                            db.commit()
                            cached_user["has_purchased"] = False
                            user_cache[cache_key] = (cached_user, cache_time)
                    return False

                # 解析过期时间并检查
                if isinstance(expires_str, datetime):
                    expires = expires_str
                else:
                    expires = datetime.fromisoformat(expires_str) if isinstance(expires_str, str) else expires_str

                if expires and expires < datetime.now():
                    # 已过期，更新数据库和缓存
                    async with get_db_context() as db:
                        user = db.query(User).filter(User.id == int(user_id)).first()
                        if user:
                            user.has_purchased = False  # type: ignore[assignment]
                            db.commit()
                            cached_user["has_purchased"] = False
                            user_cache[cache_key] = (cached_user, cache_time)
                            logger.info(f"用户购买已过期，自动禁用服务: {user.email} (ID: {user.id})")
                    return False

                # 缓存显示有效
                return True

        # ✅ 缓存不存在或已过期，从数据库加载
        async with get_db_context() as db:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                return False

            # 未购买直接拒绝
            if not cast(bool, user.has_purchased):
                return False

            expires = cast(Optional[datetime], user.purchase_expires)

            # 没有过期时间也视为无效，顺便修正数据库状态
            if not expires:
                user.has_purchased = False  # type: ignore[assignment]
                db.commit()
                if cache_key in user_cache:
                    cached_user, cache_time = user_cache[cache_key]
                    cached_user["has_purchased"] = False
                    cached_user["purchase_expires"] = None
                    user_cache[cache_key] = (cached_user, cache_time)
                return False

            # 已过期 -> 自动禁用
            if expires < datetime.now():
                user.has_purchased = False  # type: ignore[assignment]
                db.commit()
                if cache_key in user_cache:
                    cached_user, cache_time = user_cache[cache_key]
                    cached_user["has_purchased"] = False
                    cached_user["purchase_expires"] = expires
                    user_cache[cache_key] = (cached_user, cache_time)
                logger.info(f"用户购买已过期，自动禁用服务: {user.email} (ID: {user.id})")
                return False

            return True
    except Exception as e:
        logger.error(f"检查用户购买状态时发生错误: {e}")
        return False

# ============================================================
# 设备控制 — scrcpy 流媒体端点
# ============================================================

SCRCPY_SERVER_JAR = Path(__file__).parent / "scrcpy-server.jar"
SCRCPY_SERVER_VERSION = "1.19-ws7"
SCRCPY_DEVICE_PORT = 8886


async def _run_adb(*args: str, timeout: float = 15.0) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        "adb", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode(), stderr.decode(), proc.returncode or 0
    except asyncio.TimeoutError:
        proc.kill()
        raise


async def _start_scrcpy_bg(device_udid: str) -> None:
    """后台任务：在设备上启动 scrcpy 服务（fire-and-forget）。"""
    cmd = (
        f"CLASSPATH=/data/local/tmp/scrcpy-server.jar "
        f"app_process / com.genymobile.scrcpy.Server "
        f"{SCRCPY_SERVER_VERSION} web ERROR {SCRCPY_DEVICE_PORT} true"
    )
    try:
        await _run_adb("-s", device_udid, "shell", cmd, timeout=300)
    except Exception as exc:
        logger.debug(f"scrcpy 服务进程结束: {exc}")


async def _wait_scrcpy_ready(device_ip: str, port: int,
                              max_wait: float = 12.0, interval: float = 0.6) -> bool:
    """轮询直到 scrcpy WebSocket 可连接。"""
    deadline = asyncio.get_event_loop().time() + max_wait
    while asyncio.get_event_loop().time() < deadline:
        try:
            async with websockets.connect(
                f"ws://{device_ip}:{port}",
                open_timeout=1,
                close_timeout=1,
            ):
                return True
        except Exception:
            await asyncio.sleep(interval)
    return False


def _auth_from_request(request: Request):
    return request.cookies.get("access_token")


def _auth_from_ws(websocket: WebSocket):
    cookie_header = websocket.headers.get("cookie", "")
    cookies = {}
    for part in cookie_header.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            cookies[k.strip()] = v.strip()
    return cookies.get("access_token")


# ---- HTTP: 启动 scrcpy 会话 ----
@app.post("/api/device/start")
async def device_start(request: Request):
    token = _auth_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="缺少访问令牌")
    user_data = await get_current_user_from_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="无效的访问令牌")
    if not await ensure_purchase_valid(user_data["id"]):
        raise HTTPException(status_code=403, detail="服务已过期或未购买")

    blhx_ip = user_data.get("blhx_ip")
    if not blhx_ip:
        raise HTTPException(status_code=500, detail="用户没有分配 blhx_ip")
    if not SCRCPY_SERVER_JAR.exists():
        raise HTTPException(status_code=500, detail="scrcpy-server.jar 不存在")

    device_addr = f"10.10.10.{blhx_ip}"
    device_udid = f"{device_addr}:5555"

    # 1. ADB 连接
    out, _, _ = await _run_adb("connect", device_udid, timeout=10)
    logger.info(f"adb connect {device_udid}: {out.strip()}")

    # 2. 推送 JAR（已存在则跳过）
    await _run_adb("-s", device_udid, "push",
                   str(SCRCPY_SERVER_JAR), "/data/local/tmp/scrcpy-server.jar",
                   timeout=30)

    # 3. 杀掉旧实例
    await _run_adb("-s", device_udid, "shell", "pkill -f scrcpy-server", timeout=5)
    await asyncio.sleep(0.3)

    # 4. 后台启动新实例
    asyncio.create_task(_start_scrcpy_bg(device_udid))

    # 5. 等待 WebSocket 就绪
    ready = await _wait_scrcpy_ready(device_addr, SCRCPY_DEVICE_PORT)
    if not ready:
        raise HTTPException(status_code=504, detail="scrcpy 服务启动超时，请重试")

    return {"status": "ready", "device": device_udid}


# ---- HTTP: 停止 scrcpy 会话 ----
@app.post("/api/device/stop")
async def device_stop(request: Request):
    token = _auth_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="缺少访问令牌")
    user_data = await get_current_user_from_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="无效的访问令牌")

    blhx_ip = user_data.get("blhx_ip")
    if blhx_ip:
        device_udid = f"10.10.10.{blhx_ip}:5555"
        await _run_adb("-s", device_udid, "shell", "pkill -f scrcpy-server", timeout=5)
        logger.info(f"scrcpy 已停止: {device_udid}")

    return {"status": "stopped"}


# ---- WebSocket: 透明双向桥接浏览器 ↔ 设备 scrcpy ----
# 代理不解析或转换任何数据；浏览器负责全部 scrcpy 协议处理
# (解析 scrcpy_initial、发送 TYPE_CHANGE_STREAM_PARAMETERS、解码 H264)
@app.websocket("/api/device/ws")
async def device_ws_proxy(websocket: WebSocket):
    await websocket.accept()

    try:
        token = _auth_from_ws(websocket)
        if not token:
            await websocket.close(code=4001, reason="Unauthorized")
            return

        user_data = await get_current_user_from_token(token)
        if not user_data:
            await websocket.close(code=4001, reason="Invalid token")
            return

        if not await ensure_purchase_valid(user_data["id"]):
            await websocket.close(code=4003, reason="Purchase expired")
            return

        blhx_ip = user_data.get("blhx_ip")
        if not blhx_ip:
            await websocket.close(code=4004, reason="No blhx_ip")
            return

        device_url = f"ws://10.10.10.{blhx_ip}:{SCRCPY_DEVICE_PORT}"
        logger.info(f"[device_ws] 透明代理 {device_url}，用户 {user_data['email']}")

        async with websockets.connect(device_url, max_size=None, open_timeout=5) as dev_ws:

            async def browser_to_device():
                try:
                    while True:
                        msg = await websocket.receive()
                        if "bytes" in msg and msg["bytes"]:
                            await dev_ws.send(msg["bytes"])
                        elif "text" in msg and msg["text"]:
                            await dev_ws.send(msg["text"])
                        elif msg.get("type") == "websocket.disconnect":
                            break
                except Exception as exc:
                    logger.debug(f"[device_ws b→d] 结束: {exc}")

            async def device_to_browser():
                try:
                    async for frame in dev_ws:
                        if isinstance(frame, bytes):
                            await websocket.send_bytes(frame)
                        else:
                            await websocket.send_text(frame)
                except Exception as exc:
                    logger.debug(f"[device_ws d→b] 结束: {exc}")

            await asyncio.gather(browser_to_device(), device_to_browser())

    except websockets.exceptions.WebSocketException as exc:
        logger.error(f"[device_ws] 设备 WS 异常: {exc}")
    except Exception as exc:
        logger.error(f"[device_ws] 未预期错误: {exc}", exc_info=True)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ✅ 关键修复4: WebSocket代理中不持有数据库连接
@app.websocket("/{path:path}")
async def proxy_ws(websocket: WebSocket, path: str):
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

        # 检查购买是否有效（自动处理过期禁用）
        if not await ensure_purchase_valid(user_data["id"]):
            logger.warning(f"WebSocket访问被拒绝 - 用户 {user_data['email']} 套餐已过期或未购买")
            closed = True
            await websocket.close()
            return

        # 🔥 此时数据库连接已经释放，user_data是内存中的字典
        logger.info(f"WebSocket代理开始 - 用户: {user_data['email']}")

        # 确定目标服务
        host = websocket.headers.get("host", "")
        _, proxied_path = split_service_path(path)
        query_params = list(websocket.query_params.multi_items())
        filtered_query_params = [(key, value) for key, value in query_params if key != "service"]
        query_string = urlencode(filtered_query_params)
        target_ws_path = f"/{proxied_path}" if proxied_path else "/"

        target_ws_url = f"ws://10.10.10.{user_data['alas_ip']}:22267{target_ws_path}"
        logger.info(f"代理到alas: {target_ws_url}")


        if query_string:
            target_ws_url = f"{target_ws_url}?{query_string}"

        # 构建额外头部
        additional_headers = {
            "User-Agent": websocket.headers.get("user-agent") or "",
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
                        msg = await websocket.receive_text()
                        await remote_ws.send(msg)
                except Exception as e:
                    logger.debug(f"[client_to_server] 连接关闭: {e}")

            async def server_to_client():
                try:
                    while True:
                        msg = await remote_ws.recv()
                        await websocket.send_text(cast(str, msg))
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

        # 检查购买是否有效（自动处理过期禁用）
        if not await ensure_purchase_valid(user_data["id"]):
            raise HTTPException(status_code=403, detail="服务已过期或未购买")
        
        _, proxied_path = split_service_path(path)
        target_url = f"http://10.10.10.{user_data['alas_ip']}:22267/{proxied_path}"
        target_host = f"10.10.10.{user_data['alas_ip']}:22267"
       
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
                params={k: v for k, v in request.query_params.items() if k != "service"}
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



def cleanup_expired_cache():
    """清理过期的用户缓存（超过15分钟）"""
    try:
        current_time = datetime.now()
        expired_keys = []

        for cache_key, (cached_user, cache_time) in user_cache.items():
            # 如果缓存超过15分钟，标记为过期
            if (current_time - cache_time).seconds >= 900:
                expired_keys.append(cache_key)

        # 删除过期缓存
        for key in expired_keys:
            del user_cache[key]

        if expired_keys:
            logger.info(f"缓存清理完成：删除了 {len(expired_keys)} 个过期缓存条目")
    except Exception as e:
        logger.error(f"缓存清理失败: {e}")

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    import asyncio

    async def periodic_cache_cleanup():
        """定期清理过期缓存（每30分钟）"""
        while True:
            await asyncio.sleep(1800)  # 30分钟
            cleanup_expired_cache()

    # 启动后台缓存清理任务
    asyncio.create_task(periodic_cache_cleanup())
    logger.info("✅ 缓存清理任务已启动：每30分钟清理一次过期缓存")

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
