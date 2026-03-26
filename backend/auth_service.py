# -*- coding: utf-8 -*-
# 用户认证服务
import random
import asyncio
import websockets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, Response, Cookie, WebSocket
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="用户认证系统", version="1.0.0")

# 定时任务调度器
scheduler = AsyncIOScheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://alasm.gjiang.xyz:58000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "mysql+pymysql://guojiang:lpfH5a3h78@10.10.10.1:3306/DataBase"
engine = create_engine(
    DATABASE_URL,
    pool_size=10,              # 连接池大小
    max_overflow=20,           # 超出pool_size后最多再创建的连接数
    pool_recycle=1800,         # 30分钟回收连接
    pool_timeout=10,           # 获取连接的超时时间
    pool_pre_ping=True,        # 使用前检查连接是否有效
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

MAIL_CONFIG = {
    'MAIL_SERVER': 'smtp.qq.com',
    'MAIL_PORT': 465,
    'MAIL_USE_SSL': True,
    'MAIL_USERNAME': '2150757481@qq.com',
    'MAIL_PASSWORD': 'otpeqoplcckidhge'
}

SECRET_KEY = "lpfH5a3h78"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()

# 管理员认证配置（从环境变量读取）
import os
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # 默认密码，生产环境必须通过环境变量设置
ADMIN_SECRET_KEY = "admin_lpfH5a3h78"  # 管理员JWT使用独立的密钥
ADMIN_TOKEN_EXPIRE_MINUTES = 60  # 管理员token有效期60分钟

# 服务器SSH配置
SSH_HOST = "10.10.10."
SSH_USER = "root"
SSH_PASSWORD = "lpfH5a3h78"  # 请修改为实际的SSH密码

# 用户缓存，用于减少数据库查询
user_cache = {}

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
    server_ip = Column(Integer, nullable=True)

class Announcement(Base):
    __tablename__ = "announcement"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)

class SystemStatus(Base):
    __tablename__ = "system_status"
    id = Column(Integer, primary_key=True, default=1)
    is_maintenance = Column(Boolean, default=False)
    maintenance_message = Column(String(500), default="系统维护中，请稍后再试")

Base.metadata.create_all(bind=engine)

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

class AnnouncementCreate(BaseModel):
    title: str
    content: str

class MaintenanceUpdate(BaseModel):
    is_maintenance: bool
    maintenance_message: str = "系统维护中，请稍后再试"

class AdminLogin(BaseModel):
    username: str
    password: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def get_db_context():
    """异步上下文管理器，用于需要独立数据库会话的场景（如WebSocket）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
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

async def get_current_admin(admin_token: str = Cookie(None)):
    """验证管理员身份的依赖函数"""
    credentials_exception = HTTPException(
        status_code=403,
        detail="需要管理员权限",
    )
    if admin_token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(admin_token, ADMIN_SECRET_KEY, algorithms=[ALGORITHM])
        role = payload.get("role")
        if role != "admin":
            raise credentials_exception
        return {"role": "admin", "sub": payload.get("sub")}
    except JWTError:
        raise credentials_exception

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def get_current_user_from_token(access_token: str, db: Session) -> Optional[dict]:
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
            # 缓存15分钟
            if (datetime.now() - cache_time).seconds < 900:
                logger.debug(f"使用缓存的用户信息: {user_id}")
                return cached_user

        # 从数据库加载用户信息
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            user_data = {
                "id": user.id,
                "email": user.email,
                "is_active": user.is_active,
                "has_purchased": user.has_purchased,
                "alas_ip": user.alas_ip,
                "blhx_ip": user.blhx_ip,
                "ws_ip": user.ws_ip,
                "server_ip": user.server_ip
            }
            user_cache[cache_key] = (user_data, datetime.now())
            logger.info(f"从数据库加载用户信息并缓存: {user_id}")
            return user_data
    except JWTError as e:
        logger.warning(f"JWT验证失败: {e}")
    except Exception as e:
        logger.error(f"获取用户信息时出错: {e}")
    
    return None

def allocate_unique_ips(db: Session) -> tuple:
    """
    从30-99范围内顺序分配3个连续唯一的IP
    如果有空缺则优先填补空缺
    """
    # 获取所有已使用的IP
    all_users = db.query(User).all()
    used_ips = set()
    for user in all_users:
        if user.alas_ip:
            used_ips.add(user.alas_ip)
        if user.blhx_ip:
            used_ips.add(user.blhx_ip)
        if user.ws_ip:
            used_ips.add(user.ws_ip)
    
    # IP范围30-99
    available_ips = []
    for ip in range(30, 119):
        if ip not in used_ips:
            available_ips.append(ip)
    
    # 检查是否有足够的IP
    if len(available_ips) < 3:
        raise HTTPException(status_code=500, detail="可用IP不足，无法分配")
    
    # 分配前3个可用的IP（顺序分配）
    alas_ip = available_ips[0]
    blhx_ip = available_ips[1]
    ws_ip = available_ips[2]
    
    return alas_ip, blhx_ip, ws_ip

# async def send_activation_email(email: str, token: str):
#     try:
#         msg = MIMEMultipart()
#         msg['From'] = MAIL_CONFIG['MAIL_USERNAME']
#         msg['To'] = email
#         msg['Subject'] = '账户激活'
#         body = f'您的激活链接：http://alas.gjiang.xyz:58000/activate/{token}'
#         msg.attach(MIMEText(body, 'plain'))
#         server = smtplib.SMTP_SSL(MAIL_CONFIG['MAIL_SERVER'], MAIL_CONFIG['MAIL_PORT'])
#         server.login(MAIL_CONFIG['MAIL_USERNAME'], MAIL_CONFIG['MAIL_PASSWORD'])
#         text = msg.as_string()
#         server.sendmail(MAIL_CONFIG['MAIL_USERNAME'], email, text)
#         server.quit()
#         return True
#     except Exception as e:
#         print(f"邮件发送失败: {e}")
#         return False

def check_purchase_expiration(user: User, db: Session) -> bool:
    """检查单个用户的购买是否过期,如果过期则自动禁用"""
    if user.has_purchased and user.purchase_expires and user.purchase_expires < datetime.now():
        user.has_purchased = False
        db.commit()
        return True
    return False

def check_all_users_expiration():
    """定时任务:检查所有用户的购买过期状态"""
    db = SessionLocal()
    try:
        # 查询所有已购买且有过期时间的用户
        users = db.query(User).filter(
            User.has_purchased == True,
            User.purchase_expires.isnot(None)
        ).all()

        expired_count = 0
        current_time = datetime.now()

        for user in users:
            if user.purchase_expires < current_time:
                logger.info(f"定时任务检测到用户过期: {user.email} (ID: {user.id}), 过期时间: {user.purchase_expires}")
                user.has_purchased = False
                expired_count += 1

                # 清除该用户的缓存
                cache_key = f"user_{user.id}"
                if cache_key in user_cache:
                    del user_cache[cache_key]

        if expired_count > 0:
            db.commit()
            logger.info(f"定时任务完成:共禁用 {expired_count} 个过期用户")
        else:
            logger.debug("定时任务完成:没有发现过期用户")

    except Exception as e:
        logger.error(f"定时任务执行失败: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

@app.post("/register")
async def register(user_data: UserRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="该邮箱已被注册")
    
    # 分配唯一的IP（从30-99顺序分配，优先填补空缺）
    alas_ip, blhx_ip, ws_ip = allocate_unique_ips(db)
    
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        alas_ip=alas_ip,
        blhx_ip=blhx_ip,
        ws_ip=ws_ip,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"新用户注册成功: {user_data.email}, 分配IP: alas={alas_ip}, blhx={blhx_ip}, ws={ws_ip}")
    
    return {
        "msg": "注册成功",
        "user_id": new_user.id,
        "allocated_ips": {
            "alas": f"10.10.10.{alas_ip}",
            "blhx": f"10.10.10.{blhx_ip}",
            "ws": f"10.10.10.{ws_ip}"
        }
    }

@app.post("/login")
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户未激活，请查收邮件进行激活")
    purchase_expired = check_purchase_expiration(user, db)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    response = JSONResponse(content={
        "msg": "登录成功",
        "token_type": "bearer",
        "user_id": user.id,
        "alas_ip": f"10.10.10.{user.alas_ip}" if user.alas_ip else None,
        "blhx_ip": f"10.10.10.{user.blhx_ip}" if user.blhx_ip else None,
        "ws_ip": f"10.10.10.{user.ws_ip}" if user.ws_ip else None,
        "alas_port": 22267,
        "ws_port": 8000,
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
        samesite="none",
        secure=True
    )
    return response

@app.post("/purchase")
async def purchase(purchase_data: PurchaseRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.has_purchased = True
    if current_user.purchase_expires and current_user.purchase_expires > datetime.now():
        current_user.purchase_expires = current_user.purchase_expires + timedelta(days=purchase_data.days)
    else:
        current_user.purchase_expires = datetime.now() + timedelta(days=purchase_data.days)
    db.commit()
    days_remaining = (current_user.purchase_expires - datetime.now()).days
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

# ==================== 管理员认证API ====================

@app.post("/admin/login")
async def admin_login(admin_data: AdminLogin):
    """管理员登录接口 - 使用环境变量中的用户名密码"""
    if admin_data.username != ADMIN_USERNAME or admin_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 创建管理员token，使用独立的密钥和sub标识
    access_token_expires = timedelta(minutes=ADMIN_TOKEN_EXPIRE_MINUTES)
    access_token = jwt.encode(
        {
            "sub": "admin",
            "role": "admin",
            "exp": datetime.now() + access_token_expires
        },
        ADMIN_SECRET_KEY,
        algorithm=ALGORITHM
    )

    response = JSONResponse(content={
        "msg": "管理员登录成功",
        "token_type": "bearer"
    })
    response.set_cookie(
        key="admin_token",
        value=access_token,
        httponly=True,
        domain=".gjiang.xyz",
        max_age=ADMIN_TOKEN_EXPIRE_MINUTES * 60,
        samesite="none",
        secure=True
    )
    return response

@app.post("/admin/logout")
def admin_logout(response: Response):
    """管理员登出"""
    response.delete_cookie(key="admin_token", path="/", domain=".gjiang.xyz", samesite="none", secure=True)
    return {"msg": "管理员已登出"}

@app.get("/admin/check")
async def admin_check(request: Request):
    """检查管理员认证状态"""
    token = request.cookies.get("admin_token")
    if not token:
        return JSONResponse(content={"is_admin": False})
    try:
        payload = jwt.decode(token, ADMIN_SECRET_KEY, algorithms=[ALGORITHM])
        role = payload.get("role")
        if role != "admin":
            raise JWTError("Invalid role")
        return JSONResponse(content={
            "is_admin": True,
            "expires_at": payload.get("exp")
        })
    except JWTError:
        return JSONResponse(content={"is_admin": False})

@app.get("/purchase/status")
async def purchase_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        purchase_expired = check_purchase_expiration(current_user, db)
        days_remaining = 0
        if current_user.has_purchased and current_user.purchase_expires:
            delta = current_user.purchase_expires - datetime.now()
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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/user/info")
async def get_user_info(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "alas_ip": f"10.10.10.{current_user.alas_ip}" if current_user.alas_ip else None,
        "blhx_ip": f"10.10.10.{current_user.blhx_ip}" if current_user.blhx_ip else None,
        "ws_ip": f"10.10.10.{current_user.ws_ip}" if current_user.ws_ip else None,
        "alas_port": 22267,
        "ws_port": 8000,
        "has_purchased": current_user.has_purchased,
        "purchase_expires": current_user.purchase_expires.isoformat() if current_user.purchase_expires else None
    }

# ✅ 修复服务WebSocket端点 - 重启Docker容器
@app.websocket("/fix")
async def fix_service(websocket: WebSocket):
    """修复用户服务的WebSocket端点 - 重启用户的Docker容器（不持有数据库连接）"""
    await websocket.accept()

    try:
        # 🔥 第一步：验证用户身份（使用缓存，快速验证后立即释放数据库连接）
        cookie_header = websocket.headers.get("cookie", "")
        cookies = {kv.split("=")[0]: kv.split("=")[1] for kv in cookie_header.split("; ") if "=" in kv}
        token = cookies.get("access_token")

        if not token:
            await websocket.send_text("❌ 认证失败：缺少访问令牌")
            await websocket.close()
            return

        # 使用上下文管理器获取用户信息，验证后立即释放数据库连接
        async with get_db_context() as db:
            user_data = await get_current_user_from_token(token, db)
            if not user_data:
                await websocket.send_text("❌ 认证失败：无效的访问令牌")
                await websocket.close()
                return
        
        user_id = user_data['id']
        user_email = user_data['email']
        user_server = user_data['server_ip']
        
        await websocket.send_text(f"✅ 用户认证成功: {user_email}")
        await asyncio.sleep(0.5)
        
        # 🔥 第二步：开始重启Docker容器
        await websocket.send_text(f"🔧 开始修复服务（服务器：{SSH_HOST}{user_server}）...")
        await asyncio.sleep(0.5)
        
        # 定义需要重启的容器
        containers = [
            f"blhx_{user_id}",
            f"alas_{user_id}",
            f"ws-scrcpy_{user_id}"
        ]
        
        await websocket.send_text(f"📋 准备重启以下容器:")
        for container in containers:
            await websocket.send_text(f"  ➤ {container}")
        await asyncio.sleep(0.5)
        
        # 重启每个容器
        success_count = 0
        fail_count = 0
        
        for container_name in containers:
            await websocket.send_text(f"\n🔄 正在重启容器: {container_name}")
            await asyncio.sleep(0.3)
            
            try:
                # 🔥 使用sshpass进行密码认证，连接到10.10.10.227并重启容器
                ssh_command = f"sshpass -p '{SSH_PASSWORD}' ssh -o StrictHostKeyChecking=no {SSH_USER}@{SSH_HOST}{user_server} 'docker restart {container_name}'"
                
                # 执行命令
                process = await asyncio.create_subprocess_shell(
                    ssh_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=30.0
                )
                
                if process.returncode == 0:
                    await websocket.send_text(f"  ✅ {container_name} 重启成功")
                    success_count += 1
                else:
                    error_msg = stderr.decode('utf-8').strip() if stderr else "未知错误"
                    await websocket.send_text(f"  ❌ {container_name} 重启失败: {error_msg[:100]}")
                    fail_count += 1
                
            except asyncio.TimeoutError:
                await websocket.send_text(f"  ⚠️ {container_name} 重启超时")
                fail_count += 1
            except Exception as e:
                await websocket.send_text(f"  ❌ {container_name} 重启出错: {str(e)[:100]}")
                fail_count += 1
            
            await asyncio.sleep(0.5)
        
        # 🔥 第三步：完成修复
        await websocket.send_text("\n🎉 服务修复完成！")
        await asyncio.sleep(0.5)
        await websocket.send_text("📝 修复总结:")
        await websocket.send_text(f"  ➤ 用户: {user_email} (ID: {user_id})")
        await websocket.send_text(f"  ➤ 服务器: {SSH_HOST}{user_server}")
        await websocket.send_text(f"  ➤ 成功重启: {success_count} 个容器")
        if fail_count > 0:
            await websocket.send_text(f"  ➤ 失败: {fail_count} 个容器")
        await asyncio.sleep(1)
        await websocket.send_text("✨ 即将返回控制台...")
        
        logger.info(f"修复服务完成 - 用户: {user_email} (ID: {user_id}), 服务器: {SSH_HOST}{user_server}, 成功: {success_count}, 失败: {fail_count}")
        
    except websockets.exceptions.WebSocketException as e:
        logger.error(f"WebSocket异常: {e}")
    except Exception as e:
        logger.error(f"修复服务时发生错误: {e}", exc_info=True)
        try:
            await websocket.send_text(f"\n❌ 修复过程中发生错误: {str(e)[:100]}")
            await asyncio.sleep(1)
        except:
            pass
    finally:
        # 确保WebSocket关闭
        try:
            await websocket.close()
        except:
            pass

# ✅ 重连WebSocket服务 - HTTP接口，仅重启ws-scrcpy容器
@app.post("/reconnect")
async def reconnect_service(request: Request, db: Session = Depends(get_db)):
    """重连用户WebSocket服务 - 仅重启ws-scrcpy容器"""
    try:
        # 验证用户身份
        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(status_code=401, detail="缺少访问令牌")
        
        # 使用缓存获取用户信息
        user_data = await get_current_user_from_token(token, db)
        if not user_data:
            raise HTTPException(status_code=401, detail="无效的访问令牌")
        
        user_id = user_data['id']
        user_email = user_data['email']
        user_server = user_data['server_ip']
        # 只重启ws-scrcpy容器
        container_name = f"ws-scrcpy_{user_id}"
        
        logger.info(f"开始重连WebSocket服务 - 用户: {user_email} (ID: {user_id}), 容器: {container_name}")
        
        try:
            # 使用sshpass进行密码认证，连接到10.10.10.227并重启容器
            ssh_command = f"sshpass -p '{SSH_PASSWORD}' ssh -o StrictHostKeyChecking=no {SSH_USER}@{SSH_HOST}{user_server} 'docker restart {container_name}'"
            
            # 执行命令
            process = await asyncio.create_subprocess_shell(
                ssh_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0
            )
            
            if process.returncode == 0:
                logger.info(f"WebSocket容器重启成功 - 用户: {user_email}, 容器: {container_name}")
                return {
                    "success": True,
                    "message": f"容器 {container_name} 重启成功",
                    "user_email": user_email,
                    "user_id": user_id,
                    "container": container_name,
                    "server": f"{SSH_HOST}{user_server}"
                }
            else:
                error_msg = stderr.decode('utf-8').strip() if stderr else "未知错误"
                logger.error(f"WebSocket容器重启失败 - 用户: {user_email}, 容器: {container_name}, 错误: {error_msg}")
                return {
                    "success": False,
                    "message": f"容器 {container_name} 重启失败",
                    "error": error_msg[:200],
                    "user_email": user_email,
                    "user_id": user_id,
                    "container": container_name,
                    "server": f"{SSH_HOST}{user_server}"
                }
            
        except asyncio.TimeoutError:
            logger.error(f"WebSocket容器重启超时 - 用户: {user_email}, 容器: {container_name}")
            return {
                "success": False,
                "message": f"容器 {container_name} 重启超时",
                "error": "操作超时（30秒）",
                "user_email": user_email,
                "user_id": user_id,
                "container": container_name,
                "server": f"{SSH_HOST}{user_server}"
            }
        except Exception as e:
            logger.error(f"WebSocket容器重启出错 - 用户: {user_email}, 容器: {container_name}, 错误: {str(e)}")
            return {
                "success": False,
                "message": f"容器 {container_name} 重启出错",
                "error": str(e)[:200],
                "user_email": user_email,
                "user_id": user_id,
                "container": container_name,
                "server": f"{SSH_HOST}{user_server}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重连服务时发生错误: {str(e)}", exc_info=True)

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

# ✅ 应用生命周期事件:启动定时任务
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化定时任务"""
    # 添加定时任务:每1小时检查一次用户过期状态
    scheduler.add_job(
        check_all_users_expiration,
        'interval',
        hours=1,  # 每1小时执行一次
        id='check_expiration',
        name='检查用户购买过期状态',
        replace_existing=True
    )

    # 添加缓存清理定时任务:每30分钟清理一次过期缓存
    scheduler.add_job(
        cleanup_expired_cache,
        'interval',
        minutes=30,
        id='cleanup_cache',
        name='清理过期用户缓存',
        replace_existing=True
    )

    scheduler.start()
    logger.info("✅ 定时任务调度器已启动:每1小时检查用户过期状态，每30分钟清理过期缓存")

    # 启动时立即执行一次检查
    check_all_users_expiration()

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    scheduler.shutdown()
    user_cache.clear()
    logger.info("定时任务调度器已关闭，缓存已清理")

# ==================== 公告管理API ====================

@app.get("/announcement/latest")
async def get_latest_announcement(db: Session = Depends(get_db)):
    """获取最新的活跃公告"""
    announcement = db.query(Announcement).filter(
        Announcement.is_active == True
    ).order_by(Announcement.created_at.desc()).first()

    if announcement:
        return {
            "id": announcement.id,
            "title": announcement.title,
            "content": announcement.content,
            "created_at": announcement.created_at.isoformat()
        }
    return None

@app.post("/admin/announcement")
async def create_announcement(
    announcement_data: AnnouncementCreate,
    _: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """创建新公告 (仅限管理员)"""
    # 将之前的公告设为不活跃
    db.query(Announcement).filter(Announcement.is_active == True).update({"is_active": False})

    # 创建新公告
    new_announcement = Announcement(
        title=announcement_data.title,
        content=announcement_data.content,
        created_at=datetime.now(),
        is_active=True
    )
    db.add(new_announcement)
    db.commit()
    db.refresh(new_announcement)

    return {
        "success": True,
        "message": "公告发布成功",
        "announcement_id": new_announcement.id
    }

# ==================== 系统维护状态API ====================

@app.get("/system/status")
async def get_system_status(db: Session = Depends(get_db)):
    """获取系统维护状态"""
    status = db.query(SystemStatus).filter(SystemStatus.id == 1).first()

    if not status:
        # 如果不存在，创建默认状态
        status = SystemStatus(id=1, is_maintenance=False)
        db.add(status)
        db.commit()
        db.refresh(status)

    return {
        "is_maintenance": status.is_maintenance,
        "maintenance_message": status.maintenance_message
    }

@app.post("/admin/maintenance")
async def update_maintenance_status(
    maintenance_data: MaintenanceUpdate,
    _: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新系统维护状态 (仅限管理员)"""
    status = db.query(SystemStatus).filter(SystemStatus.id == 1).first()

    if not status:
        status = SystemStatus(
            id=1,
            is_maintenance=maintenance_data.is_maintenance,
            maintenance_message=maintenance_data.maintenance_message
        )
        db.add(status)
    else:
        status.is_maintenance = maintenance_data.is_maintenance
        status.maintenance_message = maintenance_data.maintenance_message

    db.commit()

    return {
        "success": True,
        "message": "维护状态更新成功",
        "is_maintenance": status.is_maintenance
    }
