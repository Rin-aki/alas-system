# -*- coding: utf-8 -*-
import random
import websockets
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks,WebSocket,Request
from urllib.parse import urlencode
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
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

# FastAPI应用实例
app = FastAPI(title="用户认证系统", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库配置
DATABASE_URL = "mysql+pymysql://guojiang:lpfH5a3h78@192.168.1.169/DataBase"
engine = create_engine(DATABASE_URL)
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
    activation_token = Column(String(255))
    token_expires = Column(DateTime)
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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
        
        body = f'您的激活链接：http://localhost:8000/activate/{token}'
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
    
    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    token = secrets.token_urlsafe(16)
    
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        alas_port=alas_port,
        blhx_port=blhx_port,
        activation_token=token,
        token_expires=datetime.utcnow() + timedelta(days=1)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 后台发送激活邮件
    background_tasks.add_task(send_activation_email, user_data.email, token)
    
    return {
        "msg": "注册成功，请查收邮件。由于您的账户已默认激活，您可以直接登录。",
        "user_id": new_user.id
    }

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_http(path: str, request: Request, db: Session = Depends(get_db)):
    parts = request.headers.get("host", "").split(":")[0].split(".")
    if len(parts) > 2:
        user_id = int(parts[0])
    else:
        raise HTTPException(status_code=404, detail="请求错误")

    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if(parts[1] == "scrcpy"):
        target_url = f"http://192.168.1.169:{user.ws_port}/{path}"
    elif(parts[1] == "alas"):
        target_url = f"http://192.168.1.169:{user.alas_port}/{path}"
    else:
        raise HTTPException(status_code=404, detail="请求错误")
    
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=dict(request.headers),
            content=await request.body()
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
    )

@app.websocket("/")
async def proxy_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    closed = False  # 标记 websocket 是否已关闭
    try:
        parts = websocket.headers.get("host", "").split(":")[0].split(".")
        if len(parts) > 2:
            user_id = int(parts[0])
        else:
            closed = True
            await websocket.close()
            return {"msg": "请求错误"}
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            closed = True
            await websocket.close()
            return {"msg": "用户不存在"}
        
        query_params = websocket.query_params
        query_string = urlencode(query_params)
        if(parts[1] == "scrcpy"):
                target_ws_url = f"ws://192.168.1.169:{user.ws_port}/?{query_string}"
        elif(parts[1] == "alas"):
            target_ws_url = f"ws://192.168.1.169:{user.alas_port}/?{query_string}"
        else:
            raise HTTPException(status_code=404, detail="请求错误")
        
        async with websockets.connect(target_ws_url) as remote_ws:
            async def client_to_server():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await remote_ws.send(data)
                except Exception:
                    pass  # 对端关闭或异常

            async def server_to_client():
                try:
                    while True:
                        data = await remote_ws.recv()
                        await websocket.send_bytes(data)
                except Exception:
                    pass  # 对端关闭或异常

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

@app.get("/activate/{token}")
async def activate(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.activation_token == token).first()
    
    if not user or user.token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="激活链接无效或已过期")
    
    user.is_active = True
    user.activation_token = None
    user.token_expires = None
    db.commit()
    
    return {"msg": "账户激活成功"}

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
    
    return {
        "msg": "登录成功",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "device_ip": "192.168.1.169",
        "alas_port": user.alas_port,
        "blhx_port": user.blhx_port,
        "email": user.email,
        "has_purchased": user.has_purchased,
        "purchase_expires": user.purchase_expires.isoformat() if user.purchase_expires else None,
        "purchase_expired": purchase_expired
    }

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

# 注释掉的Docker容器创建功能示例
# @app.post("/create_container")
# async def create_container(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
#     try:
#         # 检查用户是否已购买服务
#         if not current_user.has_purchased or check_purchase_expiration(current_user, db):
#             raise HTTPException(status_code=403, detail="用户未购买服务，无法创建容器")
#         
#         # 使用 httpx 调用 Docker API 示例
#         async with httpx.AsyncClient() as client:
#             docker_api_url = "http://localhost:2376/containers/create"
#             container_config = {
#                 "Image": "alas:latest",
#                 "name": f"alas.{current_user.id}",
#                 "HostConfig": {
#                     "PortBindings": {
#                         "80/tcp": [{"HostPort": str(current_user.alas_port)}]
#                     }
#                 }
#             }
#             response = await client.post(docker_api_url, json=container_config)
#             
#             if response.status_code == 201:
#                 container_data = response.json()
#                 return {
#                     "msg": "容器创建成功",
#                     "container_id": container_data.get("Id"),
#                     "port": current_user.alas_port
#                 }
#             else:
#                 raise HTTPException(status_code=500, detail="容器创建失败")
#         
#     except Exception as e:
#         print(f"创建容器时出错: {str(e)}")
#         raise HTTPException(status_code=500, detail="创建容器失败")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")