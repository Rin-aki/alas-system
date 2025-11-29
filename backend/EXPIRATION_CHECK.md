# 用户过期检查定时任务说明

## 功能概述

已在 `auth_service.py` 中集成了自动检查用户购买过期状态的定时任务。

## 实现方式

### 方案选择
✅ **采用集成方案** - 将定时任务集成到 auth_service.py 中

**原因:**
- 系统规模小(最多70个用户)
- 不增加额外的容器/进程
- 部署简单,维护成本低
- 可以复用现有的数据库连接和配置

### 核心功能

#### 1. 定时任务函数 `check_all_users_expiration()`
```python
def check_all_users_expiration():
    """定时任务:检查所有用户的购买过期状态"""
```

**功能:**
- 查询所有 `has_purchased=True` 且有 `purchase_expires` 的用户
- 检查过期时间是否早于当前时间
- 自动将过期用户的 `has_purchased` 设为 `False`
- 清除过期用户的缓存
- 记录日志

#### 2. 调度器配置
- 使用 `APScheduler` 的 `AsyncIOScheduler`
- **执行频率**: 每 1 小时执行一次
- **启动行为**: 应用启动时立即执行一次检查

#### 3. 日志记录
```
✅ 定时任务调度器已启动:每1小时检查用户过期状态
定时任务检测到用户过期: user@example.com (ID: 123), 过期时间: 2025-11-01 12:00:00
定时任务完成:共禁用 3 个过期用户
```

## 配置调整

### 修改检查频率

在 [auth_service.py:636-643](auth_service.py#L636-L643) 中修改:

```python
scheduler.add_job(
    check_all_users_expiration,
    'interval',
    hours=1,  # 修改这里 (可选: minutes=30, hours=2, days=1 等)
    id='check_expiration',
    name='检查用户购买过期状态',
    replace_existing=True
)
```

**常用选项:**
- `minutes=30` - 每30分钟
- `hours=2` - 每2小时
- `hours=6` - 每6小时
- `days=1` - 每天

### 使用 cron 表达式(更精确)

如果需要在特定时间执行,可以改用 cron 触发器:

```python
scheduler.add_job(
    check_all_users_expiration,
    'cron',
    hour=0,     # 每天凌晨0点
    minute=0,
    id='check_expiration',
    name='检查用户购买过期状态',
    replace_existing=True
)
```

## 部署说明

### 1. 安装依赖

已将 `apscheduler` 添加到 [requirements-auth.txt](requirements-auth.txt):

```bash
cd backend
pip install -r requirements-auth.txt
```

### 2. Docker 部署

如果使用 Docker:

```bash
# 重新构建镜像
docker-compose build auth-service

# 重启服务
docker-compose up -d auth-service
```

### 3. 验证运行

启动后查看日志:

```bash
docker-compose logs -f auth-service
```

应该看到:
```
✅ 定时任务调度器已启动:每1小时检查用户过期状态
```

## 多重保护机制

系统现在有**三层**过期检查:

1. **用户登录时** - `check_purchase_expiration()` 检查
2. **每次代理请求时** - `ensure_purchase_valid()` 检查
3. **定时任务** - 每1小时主动扫描所有用户 ⬅️ **新增**

## 注意事项

1. **数据库连接**: 定时任务使用独立的数据库会话,执行完立即释放
2. **缓存同步**: 禁用用户时会清除其缓存,确保一致性
3. **日志级别**: 过期事件记录为 `INFO`,无过期用户记录为 `DEBUG`
4. **错误处理**: 任务失败会记录错误日志并回滚事务,不影响主服务

## 测试建议

可以临时修改检查频率为 `minutes=1` 进行测试,验证功能正常后再改回 `hours=1`。
