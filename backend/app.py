# -*- coding: utf-8 -*-
import random
import docker
import websockets
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks,WebSocket,Request,HTTPException
from urllib.parse import urlencode
from fastapi.responses import Response,JSONResponse
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Cookie
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# FastAPI应用实例
app = FastAPI(title="用户认证系统", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://alasm.gjiang.xyz:58000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库配置
DATABASE_URL = "mysql+pymysql://guojiang:lpfH5a3h78@MySQL/DataBase"
engine = create_engine( DATABASE_URL,
                        pool_size=20,         # 持久连接数量
                        max_overflow=30,      # 临时额外连接
                        pool_timeout=30,      # 等待时间（秒）
                        pool_recycle=1800     # 每30分钟回收一次连接，避免MySQL断连
                       )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 邮件配置
MAIL_CONFIG = {
    'MAIL_SERVER': 'smtp.qq.com',
    'MAIL_PORT': 465,
    'MAIL_USE_SSL': True,
    'MAIL_USERNAME': '2150757481@qq.com',
    'MAIL_PASSWORD': 'otpeqoplcckidhge'
}

# JWT配置
SECRET_KEY = "lpfH5a3h78"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码加密（使用pbkdf2_sha256，无需额外依赖）
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# JWT认证
security = HTTPBearer()

# 数据库模型
class User(Base):
    __tablename__ = "user"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)  # 增加长度以支持pbkdf2
    is_active = Column(Boolean, default=True)
    has_purchased = Column(Boolean, default=False)
    purchase_expires = Column(DateTime, nullable=True)
    alas_port = Column(Integer, nullable=True)
    blhx_port = Column(Integer, nullable=True)
    ws_port = Column(Integer, nullable=True)

# 创建表
Base.metadata.create_all(bind=engine)

# Pydantic模型
class UserRegister(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class PurchaseRequest(BaseModel):
    days: int = 30

class Token(BaseModel):
    access_token: str
    token_type: str

# 依赖项
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def restart_container(container_name):
    client = docker.DockerClient(base_url='tcp://10.10.10.240:2375')
    container = client.containers.get(container_name)
    container.restart()
def exec_container(container_name,command):
    client = docker.DockerClient(base_url='tcp://10.10.10.240:2375')
    container = client.containers.get(container_name)
    exec_res = container.exec_run(command, stdout=True, stderr=True)
    return exec_res


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(access_token: str = Cookie(None), db: Session = Depends(get_db)):
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

# 辅助函数
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """加密密码"""
    return pwd_context.hash(password)

async def send_activation_email(email: str, token: str):
    """异步发送激活邮件"""
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_CONFIG['MAIL_USERNAME']
        msg['To'] = email
        msg['Subject'] = '账户激活'
        
        body = f'您的激活链接：http://alas.gjiang.xyz:58000/activate/{token}'
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP_SSL(MAIL_CONFIG['MAIL_SERVER'], MAIL_CONFIG['MAIL_PORT'])
        server.login(MAIL_CONFIG['MAIL_USERNAME'], MAIL_CONFIG['MAIL_PASSWORD'])
        text = msg.as_string()
        server.sendmail(MAIL_CONFIG['MAIL_USERNAME'], email, text)
        server.quit()
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False

def check_purchase_expiration(user: User, db: Session) -> bool:
    """检查购买是否过期"""
    if user.has_purchased and user.purchase_expires and user.purchase_expires < datetime.utcnow():
        user.has_purchased = False
        db.commit()
        return True
    return False

# API路由
@app.post("/register")
async def register(user_data: UserRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # 检查邮箱是否已存在
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="该邮箱已被注册")
    
    # 生成随机端口
    alas_port = random.randint(1024, 65535)
    blhx_port = random.randint(1024, 65535)
    ws_port = random.randint(1024, 65535)
    
    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        alas_port=alas_port,
        blhx_port=blhx_port,
        ws_port=ws_port,
        
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 后台发送激活邮件
    return {
        "msg": "注册成功",
        "user_id": new_user.id
    }


@app.websocket("/")
async def proxy_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    closed = False  # 标记 websocket 是否已关闭
    try:
        # 从 cookie 中获取 access_token（注意：WebSocket headers 中无 cookie 属性，需手动解析）
        cookie_header = websocket.headers.get("cookie", "")
        cookies = {kv.split("=")[0]: kv.split("=")[1] for kv in cookie_header.split("; ") if "=" in kv}
        token = cookies.get("access_token")
        if not token:
            closed = True
            await websocket.close()
            return

        # 解码并验证 token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                closed = True
                await websocket.close()
                return
        except JWTError:
            closed = True
            await websocket.close()
            return

        # 查询用户
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            closed = True
            await websocket.close()
            return

        # 判断服务类型（根据 Host 区分）
        host = websocket.headers.get("host", "")
        query_params = websocket.query_params
        query_string = urlencode(query_params)

        if "scrcpy" in host:
            print("scrcpy_ws请求：")
            use_bytes = True
            target_ws_url = f"ws://10.10.10.240:{user.ws_port}/?{query_string}"
        elif "alas" in host:
            print("alas_ws请求：")
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
                pass  # 已经关闭，忽略
    finally:
        if not closed:
            try:
                await websocket.close()
            except RuntimeError:
                pass  # 再次防御性处理

@app.websocket("/fix")
async def fix(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    try:
        # 从 cookie 中获取 access_token（注意：WebSocket headers 中无 cookie 属性，需手动解析）
        cookie_header = websocket.headers.get("cookie", "")
        cookies = {kv.split("=")[0]: kv.split("=")[1] for kv in cookie_header.split("; ") if "=" in kv}
        token = cookies.get("access_token")
        if not token:
            closed = True
            await websocket.close()
            return

        # 解码并验证 token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                closed = True
                await websocket.close()
                return
        except JWTError:
            closed = True
            await websocket.close()
            return

        # 查询用户
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            closed = True
            await websocket.close()
            return
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

    except HTTPException:
        await websocket.close()
        raise
    except Exception as e:
        await websocket.close()
        logger.error(f"代理过程中发生未预期错误: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")

@app.post("/login")
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户未激活，请查收邮件进行激活")
    
    # 检查购买是否过期
    purchase_expired = check_purchase_expiration(user, db)
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    print(f"用户登录: {user.email}, ID: {user.id}, 已购买: {user.has_purchased}, 过期时间: {user.purchase_expires}")
    response = JSONResponse(content={
        "msg": "登录成功",
        "token_type": "bearer",
        "user_id": user.id,
        "device_ip": "10.10.10.169",
        "alas_port": user.alas_port,
        "blhx_port": user.blhx_port,
        "email": user.email,
        "has_purchased": user.has_purchased,
        "purchase_expires": user.purchase_expires.isoformat() if user.purchase_expires else None,
        "purchase_expired": purchase_expired
    })

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        domain=".gjiang.xyz",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="none",  # 跨域安全策略
        secure=True  # 生产环境需为 True (HTTPS)
    )
    return response

@app.post("/purchase")
async def purchase(purchase_data: PurchaseRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    print(f"用户购买: {current_user.id}")
    
    # 设置购买状态和过期时间
    current_user.has_purchased = True
    
    # 如果已经有过期时间且未过期，则在原有时间基础上增加
    if current_user.purchase_expires and current_user.purchase_expires > datetime.utcnow():
        current_user.purchase_expires = current_user.purchase_expires + timedelta(days=purchase_data.days)
    else:
        current_user.purchase_expires = datetime.utcnow() + timedelta(days=purchase_data.days)
    
    db.commit()
    
    days_remaining = (current_user.purchase_expires - datetime.utcnow()).days
    
    return {
        "msg": "购买成功",
        "has_purchased": current_user.has_purchased,
        "purchase_expires": current_user.purchase_expires.isoformat(),
        "days_remaining": days_remaining
    }

@app.get("/auth/check")
async def auth_check(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return JSONResponse(content={"is_authenticated": False})

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise JWTError("Missing user ID")
        return JSONResponse(content={
            "is_authenticated": True,
            "user_id": user_id,
            "expires_at": payload.get("exp")
        })
    
    except JWTError:
        return JSONResponse(content={"is_authenticated": False})

@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token", path="/",domain=".gjiang.xyz", samesite="none", secure=True)
    return {"msg": "已登出"}

@app.get("/purchase/status")
async def purchase_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # 检查购买是否过期
        purchase_expired = check_purchase_expiration(current_user, db)
        
        # 计算剩余天数
        days_remaining = 0
        if current_user.has_purchased and current_user.purchase_expires:
            delta = current_user.purchase_expires - datetime.utcnow()
            days_remaining = delta.days if delta.days > 0 else 0
        
        return {
            "has_purchased": bool(current_user.has_purchased),
            "purchase_expires": current_user.purchase_expires.isoformat() if current_user.purchase_expires else None,
            "days_remaining": days_remaining,
            "purchase_expired": bool(purchase_expired)
        }
        
    except Exception as e:
        print(f"获取购买状态错误: {str(e)}")
        raise HTTPException(status_code=500, detail="获取购买状态失败")

# 后台任务：定期检查购买状态
async def check_all_purchases_task():
    """定期检查所有用户的购买状态"""
    while True:
        try:
            db = SessionLocal()
            # 获取所有已购买但可能过期的用户
            users = db.query(User).filter(User.has_purchased == True).all()
            now = datetime.utcnow()
            
            for user in users:
                if user.purchase_expires and user.purchase_expires < now:
                    user.has_purchased = False
                    print(f"用户 {user.email} 的购买已过期")
            
            db.commit()
            db.close()
            print(f"[{datetime.now()}] 已检查所有用户的购买状态")
        except Exception as e:
            print(f"检查购买状态时出错: {e}")
        
        # 每小时检查一次
        await asyncio.sleep(3600)

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    # 启动后台任务
    asyncio.create_task(check_all_purchases_task())
    print("应用启动完成，后台任务已开始运行")
    print("密码加密方案：PBKDF2-SHA256（无需额外依赖）")

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# 获取用户信息（新增接口）
@app.get("/user/info")
async def get_user_info(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "alas_port": current_user.alas_port,
        "blhx_port": current_user.blhx_port,
        "has_purchased": current_user.has_purchased,
        "purchase_expires": current_user.purchase_expires.isoformat() if current_user.purchase_expires else None
    }

# HTTP客户端配置 - 修改了超时设置
client = httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=5.0,    # 连接超时
        read=30.0,      # 读取超时，适应可能的慢响应
        write=10.0,     # 写入超时
        pool=10.0       # 连接池超时
    ),
    limits=httpx.Limits(
        max_connections=100, 
        max_keepalive_connections=20
    ),
    follow_redirects=True  # 跟随重定向，处理SPA路由
)

def get_user_sync(db, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

# 需要排除的响应头 - 增加了更多头部
EXCLUDED_RESPONSE_HEADERS = {
    "content-length",
    "transfer-encoding",
    "content-encoding",
    "connection",
    "upgrade",
    "proxy-authenticate",
    "proxy-authorization"
}

# 需要排除的请求头 - 增加了更多头部
EXCLUDED_REQUEST_HEADERS = {
    "host",
    "connection",
    "content-length",
    "upgrade",
    "proxy-connection"
}

def prepare_proxy_headers(request: Request) -> dict:
    """准备代理头信息"""
    # 过滤原始请求头
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in EXCLUDED_REQUEST_HEADERS
    }
    
    # 获取客户端信息
    client_ip = request.client.host if request.client else "unknown"
    original_host = request.headers.get("host", "")
    scheme = request.url.scheme
    port = request.url.port or (443 if scheme == "https" else 80)
    
    # 添加代理头信息
    forward_headers["X-Forwarded-For"] = request.headers.get("x-forwarded-for", client_ip)
    forward_headers["X-Forwarded-Host"] = request.headers.get("x-forwarded-host", original_host)
    forward_headers["X-Forwarded-Proto"] = request.headers.get("x-forwarded-proto", scheme)
    forward_headers["X-Forwarded-Port"] = request.headers.get("x-forwarded-port", str(port))
    
    # X-Real 头信息（备用格式）
    forward_headers["X-Real-IP"] = request.headers.get("x-real-ip", client_ip)
    forward_headers["X-Real-Proto"] = forward_headers["X-Forwarded-Proto"]
    
    # 保存原始Host
    forward_headers["X-Original-Host"] = original_host
    
    return forward_headers

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_http(path: str, request: Request, db: Session = Depends(get_db)):
    try:
        # 从 Cookie 获取 token
        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(status_code=401, detail="缺少访问令牌")

        # 解码并验证 token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="无效的访问令牌")
        except JWTError:
            raise HTTPException(status_code=401, detail="访问令牌验证失败")

        # 查询用户
        user = await asyncio.to_thread(get_user_sync, db, int(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
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

        # 构造请求头
        forward_headers = prepare_proxy_headers(request)
        forward_headers["Host"] = target_host

        # 读取请求体
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()

        # 发起转发请求
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

        # 过滤响应头
        response_headers = {
            k: v for k, v in proxied_response.headers.items()
            if k.lower() not in EXCLUDED_RESPONSE_HEADERS
        }

        # 处理CORS（如果需要）
        if "access-control-allow-origin" not in [h.lower() for h in response_headers.keys()]:
            origin = request.headers.get("origin")
            if origin:
                response_headers["Access-Control-Allow-Origin"] = origin
                response_headers["Access-Control-Allow-Credentials"] = "true"

        # 记录响应信息用于调试
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

# 应用关闭时清理资源
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    await client.aclose()
    logger.info("HTTP客户端已关闭")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")