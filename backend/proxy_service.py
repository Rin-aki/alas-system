# -*- coding: utf-8 -*-
# 反向代理服务
import asyncio
import docker
import websockets
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, WebSocket, Request
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from jose import JWTError, jwt
import httpx
import logging
from urllib.parse import urlencode

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
engine = create_engine(DATABASE_URL)
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

Base.metadata.create_all(bind=engine)

# JWT校验
async def get_current_user(access_token: str, db: Session):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if access_token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user

def restart_container(container_name):
    client = docker.DockerClient(base_url='tcp://10.10.10.240:2375')
    container = client.containers.get(container_name)
    container.restart()

def exec_container(container_name,command):
    client = docker.DockerClient(base_url='tcp://10.10.10.240:2375')
    container = client.containers.get(container_name)
    exec_res = container.exec_run(command, stdout=True, stderr=True)
    return exec_res

@app.websocket("/")
async def proxy_ws(websocket: WebSocket):
    await websocket.accept()
    db = SessionLocal()
    closed = False
    try:
        cookie_header = websocket.headers.get("cookie", "")
        cookies = {kv.split("=")[0]: kv.split("=")[1] for kv in cookie_header.split("; ") if "=" in kv}
        token = cookies.get("access_token")
        if not token:
            closed = True
            await websocket.close()
            return
        user = await get_current_user(token, db)
        host = websocket.headers.get("host", "")
        query_params = websocket.query_params
        query_string = urlencode(query_params)
        if "scrcpy" in host:
            use_bytes = True
            target_ws_url = f"ws://10.10.10.240:{user.ws_port}/?{query_string}"
        elif "alas" in host:
            use_bytes = False
            target_ws_url = f"ws://10.10.10.240:{user.alas_port}/?{query_string}"
        else:
            closed = True
            await websocket.close()
            return
        async with websockets.connect(target_ws_url) as remote_ws:
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
                    print(f"[client_to_server] exception: {e}")
            async def server_to_client():
                try:
                    while True:
                        msg = await remote_ws.recv()
                        if use_bytes:
                            await websocket.send_bytes(msg)
                        else:
                            await websocket.send_text(msg)
                except Exception as e:
                    print(f"[server_to_client] exception: {e}")
            await asyncio.gather(client_to_server(), server_to_client())
    except Exception as e:
        print(f"WebSocket连接失败: {e}")
        if not closed:
            closed = True
            try:
                await websocket.close()
            except RuntimeError:
                pass
    finally:
        db.close()
        if not closed:
            try:
                await websocket.close()
            except RuntimeError:
                pass

@app.websocket("/fix")
async def fix(websocket: WebSocket):
    await websocket.accept()
    db = SessionLocal()
    try:
        cookie_header = websocket.headers.get("cookie", "")
        cookies = {kv.split("=")[0]: kv.split("=")[1] for kv in cookie_header.split("; ") if "=" in kv}
        token = cookies.get("access_token")
        if not token:
            await websocket.close()
            return
        user = await get_current_user(token, db)
        await websocket.send_text(f"正在重启容器 ws-scrcpy...")
        await websocket.send_text(f"正在重启容器 alas...")
        await websocket.send_text(f"正在重启容器 碧蓝航线虚拟机...")
        container_names = ["ws-scrcpy_"+str(user.id), "alas_"+str(user.id), "blhx_"+str(user.id)]
        for container_name in container_names:
            try:
                await asyncio.to_thread(restart_container,container_name)
                await websocket.send_text(f"容器 {container_name} 重启成功")
            except docker.errors.NotFound:
                await websocket.send_text(f"容器 {container_name} 未找到")
            except docker.errors.APIError as e:
                await websocket.send_text(f"重启容器 {container_name} 失败: {str(e)}")
        await websocket.send_text("所有容器重启完成")
        await asyncio.sleep(3)
        exec_result = await asyncio.to_thread(exec_container,"ws-scrcpy_"+str(user.id),"adb connect 10.10.10.240:"+str(user.blhx_port))
        await websocket.send_text(exec_result.output.decode())
        await websocket.send_text("scrcpy已与碧蓝航线建立连接")
        await websocket.close()
    except Exception as e:
        await websocket.close()
        logger.error(f"代理过程中发生未预期错误: {str(e)}")
    finally:
        db.close()

client = httpx.AsyncClient()

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
    forward_headers["X-Forwarded-For"] = request.headers.get("x-forwarded-for", client_ip)
    forward_headers["X-Forwarded-Host"] = request.headers.get("x-forwarded-host", original_host)
    forward_headers["X-Forwarded-Proto"] = request.headers.get("x-forwarded-proto", scheme)
    forward_headers["X-Forwarded-Port"] = request.headers.get("x-forwarded-port", str(port))
    forward_headers["X-Real-IP"] = request.headers.get("x-real-ip", client_ip)
    forward_headers["X-Real-Proto"] = forward_headers["X-Forwarded-Proto"]
    forward_headers["X-Original-Host"] = original_host
    return forward_headers

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_http(path: str, request: Request):
    db = SessionLocal()
    try:
        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(status_code=401, detail="缺少访问令牌")
        user = await get_current_user(token, db)
        host = request.headers.get("host", "")
        if "scrcpy" in host:
            target_url = f"http://10.10.10.240:{user.ws_port}/{path}"
            target_host = f"10.10.10.240:{user.ws_port}"
        elif "alas" in host:
            target_url = f"http://10.10.10.240:{user.alas_port}/{path}"
            target_host = f"10.10.10.240:{user.alas_port}"
        else:
            raise HTTPException(status_code=404, detail="未知的服务域名")
        logger.info(f"代理请求: {request.method} {request.url} -> {target_url}")
        forward_headers = prepare_proxy_headers(request)
        forward_headers["Host"] = target_host
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
        try:
            proxied_response = await client.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body,
                params=dict(request.query_params)
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
        response_headers = {
            k: v for k, v in proxied_response.headers.items()
            if k.lower() not in EXCLUDED_RESPONSE_HEADERS
        }
        if "access-control-allow-origin" not in [h.lower() for h in response_headers.keys()]:
            origin = request.headers.get("origin")
            if origin:
                response_headers["Access-Control-Allow-Origin"] = origin
                response_headers["Access-Control-Allow-Credentials"] = "true"
        logger.debug(f"响应状态: {proxied_response.status_code}, Content-Type: {proxied_response.headers.get('content-type', 'unknown')}")
        return Response(
            content=proxied_response.content,
            status_code=proxied_response.status_code,
            headers=response_headers,
            media_type=proxied_response.headers.get("content-type")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"代理过程中发生未预期错误: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")
    finally:
        db.close()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6300, log_level="info")
