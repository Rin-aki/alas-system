# -*- coding: utf-8 -*-
# 用户认证服务
import random
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, Response, Cookie
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="用户认证系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://alasm.gjiang.xyz:58000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "mysql+pymysql://guojiang:lpfH5a3h78@MySQL/DataBase"
engine = create_engine(DATABASE_URL)
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

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

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
    if user.has_purchased and user.purchase_expires and user.purchase_expires < datetime.utcnow():
        user.has_purchased = False
        db.commit()
        return True
    return False

@app.post("/register")
async def register(user_data: UserRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="该邮箱已被注册")
    alas_port = random.randint(1024, 65535)
    blhx_port = random.randint(1024, 65535)
    ws_port = random.randint(1024, 65535)
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
    return {
        "msg": "注册成功",
        "user_id": new_user.id
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
        samesite="none",
        secure=True
    )
    return response

@app.post("/purchase")
async def purchase(purchase_data: PurchaseRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.has_purchased = True
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
        purchase_expired = check_purchase_expiration(current_user, db)
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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6200, log_level="info")
