# 抖音自动化运营系统设计文档

## 1. 系统概述
本系统是一个基于Python的抖音自动化运营工具，主要功能包括视频评论、粉丝关注、私信互动等。系统通过模拟真实用户操作，实现账号的自动化运营和粉丝维护。

## 2. 系统架构
系统采用模块化设计，主要包含以下模块：
- 浏览器控制模块（BrowserHelper）
- 数据库管理模块（DB）
- 任务运行模块（TaskRunner）
- 视频评论模块（VideoCommentManager）
- 粉丝关注模块（FollowFansManager）
- 私信管理模块（MessageManager）
- 配置管理模块（Config）
- 日志管理模块（Logger）

## 3. 功能模块说明

### 3.1 浏览器控制模块（BrowserHelper）
负责浏览器的启动、页面访问、元素定位等基础操作。
- 启动Chrome浏览器
- 管理浏览器会话
- 提供页面操作方法
- 处理浏览器异常

### 3.2 数据库管理模块（DB）
使用SQLite数据库存储运营数据。主要表结构：
- follows：关注记录表
- follow_fans：待关注粉丝表
- fans：粉丝记录表
- messages：私信记录表
- processed_videos：已处理视频表
- interactions：互动记录表

### 3.3 任务运行模块（TaskRunner）
负责调度和执行各类任务：
- 视频评论任务
- 粉丝关注任务
- 取消关注任务
- 私信互动任务

### 3.4 视频评论模块（VideoCommentManager）
管理视频评论相关功能：
- 获取目标视频
- 发表评论
- 记录评论历史
- 控制评论频率

### 3.5 粉丝关注模块（FollowFansManager）
处理粉丝关注相关操作：
- 获取潜在粉丝
- 执行关注操作
- 管理关注记录
- 执行取消关注

### 3.6 私信管理模块（MessageManager）
负责粉丝私信互动：
- 新粉丝三天私信互动
- 私信模板管理
- 私信发送控制
- 互动记录管理

功能特点：
1. 自动识别新粉丝
2. 根据关注天数发送不同私信
3. 控制私信频率和数量
4. 记录私信历史
5. 评估粉丝互动效果

私信互动流程：
1. 第一天：发送欢迎私信
2. 第二天：发送互动私信
3. 第三天：发送总结私信
4. 根据互动情况标记有效粉丝

### 3.7 配置管理模块（Config）
管理系统配置信息：
- 账号信息
- 浏览器配置
- 数据库配置
- 操作频率限制
- 私信模板配置
- 日志配置

### 3.8 日志管理模块（Logger）
记录系统运行日志：
- 操作日志
- 错误日志
- 统计信息
- 截图记录

## 4. 数据库设计

### 4.1 follows表
```sql
CREATE TABLE follows (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    follow_time TIMESTAMP,
    unfollow_time TIMESTAMP,
    is_following INTEGER DEFAULT 1,
    should_unfollow INTEGER DEFAULT 0,
    marked_for_unfollow_time TIMESTAMP
)
```

### 4.2 follow_fans表
```sql
CREATE TABLE follow_fans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    username TEXT,
    from_type TEXT,
    source_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER DEFAULT 0,
    UNIQUE(user_id)
)
```

### 4.3 fans表
```sql
CREATE TABLE fans (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    first_seen_time TIMESTAMP,
    last_seen_time TIMESTAMP,
    follow_status TEXT,
    is_processed INTEGER DEFAULT 0,
    need_follow_back INTEGER DEFAULT 0,
    follow_back_time TIMESTAMP,
    days_followed INTEGER DEFAULT 0,
    last_message_time TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    is_valid_fan INTEGER DEFAULT 0
)
```

### 4.4 messages表
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    message TEXT,
    send_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES fans (user_id)
)
```

### 4.5 processed_videos表
```sql
CREATE TABLE processed_videos (
    video_url TEXT PRIMARY KEY,
    processed_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success INTEGER DEFAULT 1
)
```

### 4.6 interactions表
```sql
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action_type TEXT,
    action_time TIMESTAMP,
    UNIQUE(user_id, action_type, action_time)
)
```

## 5. 配置说明

### 5.1 基础配置
```yaml
base:
  username: "your_username"  # 抖音账号用户名
  password: "your_password"  # 抖音账号密码
```

### 5.2 浏览器配置
```yaml
browser:
  executable_path: "chrome.exe路径"
  user_data_dir: "用户数据目录"
  headless: false
```

### 5.3 操作配置
```yaml
operation:
  video_comment:
    enabled: true
    max_videos_per_day: 50
    max_comments_per_video: 3
  
  follow:
    enabled: true
    max_follows_per_day: 100
    unfollow_days: 7
    max_unfollows_per_day: 50
    
  message:
    enabled: true
    max_messages_per_day: 100
    batch_size: 50
```

### 5.4 私信模板配置
```yaml
message:
  templates:
    day1:
      - "你好呀，很高兴认识你~"
      - "Hi，我是{username}，谢谢你的关注！"
    day2:
      - "最近在忙什么呢？"
      - "今天过得怎么样呀？"
    day3:
      - "这几天聊得很开心，希望以后也能经常互动~"
      - "感谢这几天的交流，你真的很有趣！"
```

## 6. 使用说明

### 6.1 环境要求
- Python 3.8+
- Chrome浏览器
- SQLite数据库

### 6.2 安装依赖
```bash
pip install -r requirements.txt
```

### 6.3 配置文件
1. 复制config.yaml.example为config.yaml
2. 修改账号信息和其他配置

### 6.4 运行系统
```bash
python main.py
```

## 7. 注意事项
1. 遵守抖音平台规则
2. 合理控制操作频率
3. 定期备份数据库
4. 及时处理异常情况
5. 监控系统运行状态 