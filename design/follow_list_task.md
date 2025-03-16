# 关注列表相关任务设计文档

## 1. 概述

本文档详细描述抖音自动化工具中与关注列表管理相关的任务设计，包括关注用户管理、取消关注、关注状态监控等功能。

## 2. 数据库设计

### 2.1 关注记录表 (follows)

| 字段名 | 类型 | 说明 |
|-------|------|------|
| user_id | TEXT | 用户ID，主键 |
| username | TEXT | 用户名 |
| follow_time | TIMESTAMP | 关注时间 |
| unfollow_time | TIMESTAMP | 取消关注时间 |
| is_following | INTEGER | 是否正在关注，1表示是，0表示否 |
| follow_days | INTEGER | 已关注天数 |
| follow_back | INTEGER | 是否回关，1表示是，0表示否 |
| unfollow_reason | TEXT | 取消关注原因 |
| from_fan | INTEGER | 是否来自粉丝，1表示是，0表示否 |
| last_interaction_time | TIMESTAMP | 最后互动时间 |
| unfollow_attempts | INTEGER | 取消关注尝试次数 |
| last_unfollow_attempt | TIMESTAMP | 最后一次尝试取消关注时间 |

### 2.2 互动记录表 (interactions)

| 字段名 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 自增主键 |
| user_id | TEXT | 用户ID，外键关联follows表 |
| interaction_type | TEXT | 互动类型（like, comment, message等） |
| interaction_time | TIMESTAMP | 互动时间 |
| content | TEXT | 互动内容 |
| source_id | TEXT | 互动来源ID，如视频ID |

## 3. 关注用户管理功能

### 3.1 功能描述

该功能负责管理已关注的用户，包括添加新关注、更新关注状态、获取关注列表等。

### 3.2 处理流程

```
开始
  |
  v
检查用户是否已在关注表中 --> 存在 --> 更新关注记录
  |
  v (不存在)
添加新关注记录
  |
  v
设置关注状态和属性
  |
  v
提交数据库事务
  |
  v
结束
```

### 3.3 主要方法

#### 3.3.1 add_follow_record

```python
def add_follow_record(self, user_id, username, from_fan=0):
    """
    添加新的关注记录
    
    参数:
        user_id: 用户ID
        username: 用户名
        from_fan: 是否来自粉丝，1表示是，0表示否
    """
    try:
        now = datetime.now()
        cursor = self.conn.cursor()
        
        # 检查是否已存在该关注记录
        cursor.execute("SELECT user_id FROM follows WHERE user_id = ?", (user_id,))
        existing_follow = cursor.fetchone()
        
        if existing_follow:
            # 更新关注记录
            cursor.execute(
                """
                UPDATE follows 
                SET follow_time = ?,
                    is_following = 1,
                    unfollow_time = NULL,
                    from_fan = ?
                WHERE user_id = ?
                """,
                (now, from_fan, user_id)
            )
            logger.info(f"更新关注记录: {username} ({user_id})")
        else:
            # 添加新的关注记录
            cursor.execute(
                """
                INSERT INTO follows (
                    user_id, username, follow_time, is_following,
                    follow_days, follow_back, from_fan
                ) VALUES (?, ?, ?, 1, 0, ?, ?)
                """,
                (user_id, username, now, from_fan, from_fan)
            )
            logger.info(f"添加新关注记录: {username} ({user_id})")
        
        self.conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"添加关注记录失败: {str(e)}")
        return False
```

#### 3.3.2 get_follow_by_id

```python
def get_follow_by_id(self, user_id):
    """
    根据用户ID获取关注信息
    
    参数:
        user_id: 用户ID
        
    返回:
        dict: 包含关注信息的字典，如果用户不存在则返回None
    """
    try:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM follows WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, row))
        return None
        
    except Exception as e:
        logger.error(f"获取关注信息失败: {str(e)}")
        return None
```

#### 3.3.3 update_follow_days

```python
def update_follow_days(self):
    """更新所有关注用户的关注天数"""
    try:
        cursor = self.conn.cursor()
        now = datetime.now()
        
        # 更新关注天数
        cursor.execute(
            """
            UPDATE follows 
            SET follow_days = CAST(julianday(date(?)) - julianday(date(follow_time)) AS INTEGER)
            WHERE is_following = 1
            """,
            (now,)
        )
        
        self.conn.commit()
        logger.info("已更新所有关注用户的关注天数")
        return True
        
    except Exception as e:
        logger.error(f"更新关注天数失败: {str(e)}")
        return False
```

## 4. 取消关注功能

### 4.1 功能描述

该功能负责取消关注不活跃或不符合条件的用户，包括获取需要取消关注的用户、执行取消关注操作、记录取消关注状态等。

### 4.2 处理流程

```
开始
  |
  v
获取需要取消关注的用户列表
  |
  v
循环处理每个用户 --> 用户列表为空 --> 结束
  |
  v (有用户)
检查取消关注频率限制 --> 超过限制 --> 跳过当前用户
  |
  v (未超过限制)
访问用户主页
  |
  v
点击取消关注按钮
  |
  v
确认取消关注
  |
  v
检查取消关注结果 --> 失败 --> 记录失败原因和重试信息
  |
  v (成功)
更新取消关注记录
  |
  v
继续处理下一个用户
```

### 4.3 主要方法

#### 4.3.1 get_users_to_unfollow

```python
def get_users_to_unfollow(self, limit=50):
    """
    获取需要取消关注的用户
    
    参数:
        limit: 最大返回数量
        
    返回:
        包含用户ID和用户名的字典列表 [{'user_id': '123', 'username': 'user1'}, ...]
    """
    try:
        cursor = self.conn.cursor()
        now = datetime.now()
        
        # 获取需要取消关注的用户
        cursor.execute(
            """
            SELECT user_id, username, follow_days, unfollow_attempts
            FROM follows
            WHERE is_following = 1
            AND (
                -- 关注超过7天且不是粉丝的用户
                (follow_days >= 7 AND from_fan = 0)
                OR
                -- 关注超过14天且是粉丝但没有回关的用户
                (follow_days >= 14 AND from_fan = 1 AND follow_back = 0)
            )
            AND (
                -- 从未尝试取消关注
                unfollow_attempts IS NULL
                OR
                -- 上次尝试取消关注已经过去至少1天
                (julianday(date(?)) - julianday(date(last_unfollow_attempt)) >= 1)
            )
            ORDER BY follow_days DESC
            LIMIT ?
            """,
            (now, limit)
        )
        
        # 获取列名
        columns = [description[0] for description in cursor.description]
        
        # 获取结果
        rows = cursor.fetchall()
        
        # 将结果转换为字典列表
        users = []
        for row in rows:
            user_dict = dict(zip(columns, row))
            users.append(user_dict)
        
        return users
        
    except Exception as e:
        logger.error(f"获取需要取消关注的用户失败: {str(e)}")
        return []
```

#### 4.3.2 mark_user_unfollowed

```python
def mark_user_unfollowed(self, user_id, reason="inactive"):
    """
    标记用户已取消关注
    
    参数:
        user_id: 用户ID
        reason: 取消关注原因
        
    返回:
        bool: 是否成功标记
    """
    try:
        now = datetime.now()
        cursor = self.conn.cursor()
        
        # 更新关注记录
        cursor.execute(
            """
            UPDATE follows 
            SET is_following = 0,
                unfollow_time = ?,
                unfollow_reason = ?
            WHERE user_id = ?
            """,
            (now, reason, user_id)
        )
        
        self.conn.commit()
        logger.info(f"已标记用户 {user_id} 为已取消关注，原因: {reason}")
        return True
        
    except Exception as e:
        logger.error(f"标记用户已取消关注失败: {str(e)}")
        return False
```

#### 4.3.3 update_unfollow_attempt

```python
def update_unfollow_attempt(self, user_id, success=False):
    """
    更新取消关注尝试记录
    
    参数:
        user_id: 用户ID
        success: 是否成功取消关注
        
    返回:
        bool: 是否成功更新
    """
    try:
        now = datetime.now()
        cursor = self.conn.cursor()
        
        # 获取当前尝试次数
        cursor.execute(
            "SELECT unfollow_attempts FROM follows WHERE user_id = ?",
            (user_id,)
        )
        
        result = cursor.fetchone()
        current_attempts = result[0] if result and result[0] is not None else 0
        
        # 更新尝试记录
        cursor.execute(
            """
            UPDATE follows 
            SET unfollow_attempts = ?,
                last_unfollow_attempt = ?
            WHERE user_id = ?
            """,
            (current_attempts + 1, now, user_id)
        )
        
        self.conn.commit()
        logger.info(f"已更新用户 {user_id} 的取消关注尝试记录，当前尝试次数: {current_attempts + 1}")
        return True
        
    except Exception as e:
        logger.error(f"更新取消关注尝试记录失败: {str(e)}")
        return False
```

#### 4.3.4 unfollow_user

```python
def unfollow_user(self, user_id, username):
    """
    取消关注指定用户
    
    参数:
        user_id: 用户ID
        username: 用户名
        
    返回:
        bool: 是否成功取消关注
    """
    try:
        # 访问用户主页
        logger.info(f"访问用户主页准备取消关注: {username} ({user_id})")
        self.driver.get(f"https://www.douyin.com/user/{user_id}")
        self.random_sleep(3, 5)
        
        # 保存页面截图
        save_screenshot(self.driver, f"unfollow_{user_id}", level="NORMAL")
        
        # 查找已关注按钮
        followed_button = None
        followed_button_selectors = [
            "//button[contains(@class, 'semi-button-primary')]//span[text()='已关注']/parent::button",
            "//button//span[text()='已关注']/parent::button"
        ]
        
        for selector in followed_button_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        followed_button = element
                        logger.info(f"找到已关注按钮: {selector}")
                        break
                if followed_button:
                    break
            except:
                continue
        
        if not followed_button:
            logger.warning(f"未找到已关注按钮: {username} ({user_id})")
            # 更新尝试记录
            self.update_unfollow_attempt(user_id, success=False)
            return False
        
        # 点击已关注按钮
        logger.info(f"点击已关注按钮: {username} ({user_id})")
        try:
            followed_button.click()
            self.random_sleep(2, 3)
        except:
            try:
                self.driver.execute_script("arguments[0].click();", followed_button)
                self.random_sleep(2, 3)
            except Exception as e:
                logger.error(f"点击已关注按钮失败: {str(e)}")
                # 更新尝试记录
                self.update_unfollow_attempt(user_id, success=False)
                return False
        
        # 查找取消关注确认按钮
        unfollow_confirm_button = None
        unfollow_confirm_selectors = [
            "//div[contains(@class, 'semi-modal-content')]//button[contains(@class, 'semi-button-danger')]",
            "//div[contains(@class, 'modal-content')]//button[contains(@class, 'danger')]"
        ]
        
        for selector in unfollow_confirm_selectors:
            try:
                unfollow_confirm_button = self.driver.find_element(By.XPATH, selector)
                logger.info(f"找到取消关注确认按钮: {selector}")
                break
            except:
                continue
        
        if not unfollow_confirm_button:
            logger.warning(f"未找到取消关注确认按钮: {username} ({user_id})")
            # 更新尝试记录
            self.update_unfollow_attempt(user_id, success=False)
            return False
        
        # 点击取消关注确认按钮
        logger.info(f"点击取消关注确认按钮: {username} ({user_id})")
        try:
            unfollow_confirm_button.click()
            self.random_sleep(2, 3)
        except:
            try:
                self.driver.execute_script("arguments[0].click();", unfollow_confirm_button)
                self.random_sleep(2, 3)
            except Exception as e:
                logger.error(f"点击取消关注确认按钮失败: {str(e)}")
                # 更新尝试记录
                self.update_unfollow_attempt(user_id, success=False)
                return False
        
        # 检查是否取消关注成功
        try:
            # 等待关注按钮出现
            self.wait.until(lambda d: len(d.find_elements(By.XPATH, "//button//span[text()='关注']/parent::button")) > 0)
            
            # 标记用户已取消关注
            self.mark_user_unfollowed(user_id, reason="inactive")
            
            # 更新尝试记录
            self.update_unfollow_attempt(user_id, success=True)
            
            logger.info(f"成功取消关注用户: {username} ({user_id})")
            return True
            
        except Exception as e:
            logger.warning(f"无法确认取消关注是否成功: {str(e)}")
            # 更新尝试记录
            self.update_unfollow_attempt(user_id, success=False)
            return False
            
    except Exception as e:
        logger.error(f"取消关注失败: {str(e)}")
        # 更新尝试记录
        self.update_unfollow_attempt(user_id, success=False)
        return False
```

## 5. 关注状态监控功能

### 5.1 功能描述

该功能负责监控关注状态，包括检查用户是否回关、更新互动记录、识别不活跃用户等。

### 5.2 处理流程

```
开始
  |
  v
获取需要检查的关注用户列表
  |
  v
循环处理每个用户 --> 用户列表为空 --> 结束
  |
  v (有用户)
访问用户主页
  |
  v
检查用户是否回关 --> 已回关 --> 更新回关状态
  |
  v (未回关)
检查用户活跃度
  |
  v
更新用户互动记录
  |
  v
继续处理下一个用户
```

### 5.3 主要方法

#### 5.3.1 get_follows_to_check

```python
def get_follows_to_check(self, limit=50):
    """
    获取需要检查的关注用户
    
    参数:
        limit: 最大返回数量
        
    返回:
        包含用户ID和用户名的字典列表 [{'user_id': '123', 'username': 'user1'}, ...]
    """
    try:
        cursor = self.conn.cursor()
        now = datetime.now()
        
        # 获取需要检查的关注用户
        cursor.execute(
            """
            SELECT user_id, username, follow_days, follow_back
            FROM follows
            WHERE is_following = 1
            AND (
                -- 从未检查过回关状态的用户
                follow_back IS NULL
                OR
                -- 已关注但未回关且关注天数小于7天的用户
                (follow_back = 0 AND follow_days < 7)
            )
            ORDER BY follow_time ASC
            LIMIT ?
            """,
            (limit,)
        )
        
        # 获取列名
        columns = [description[0] for description in cursor.description]
        
        # 获取结果
        rows = cursor.fetchall()
        
        # 将结果转换为字典列表
        users = []
        for row in rows:
            user_dict = dict(zip(columns, row))
            users.append(user_dict)
        
        return users
        
    except Exception as e:
        logger.error(f"获取需要检查的关注用户失败: {str(e)}")
        return []
```

#### 5.3.2 update_follow_back_status

```python
def update_follow_back_status(self, user_id, follow_back=0):
    """
    更新用户回关状态
    
    参数:
        user_id: 用户ID
        follow_back: 是否回关，1表示是，0表示否
        
    返回:
        bool: 是否成功更新
    """
    try:
        cursor = self.conn.cursor()
        
        # 更新回关状态
        cursor.execute(
            """
            UPDATE follows 
            SET follow_back = ?
            WHERE user_id = ?
            """,
            (follow_back, user_id)
        )
        
        self.conn.commit()
        logger.info(f"已更新用户 {user_id} 的回关状态: {follow_back}")
        return True
        
    except Exception as e:
        logger.error(f"更新回关状态失败: {str(e)}")
        return False
```

#### 5.3.3 add_interaction_record

```python
def add_interaction_record(self, user_id, interaction_type, content=None, source_id=None):
    """
    添加互动记录
    
    参数:
        user_id: 用户ID
        interaction_type: 互动类型（like, comment, message等）
        content: 互动内容
        source_id: 互动来源ID，如视频ID
        
    返回:
        bool: 是否成功添加
    """
    try:
        now = datetime.now()
        cursor = self.conn.cursor()
        
        # 添加互动记录
        cursor.execute(
            """
            INSERT INTO interactions (
                user_id, interaction_type, interaction_time, content, source_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, interaction_type, now, content, source_id)
        )
        
        # 更新最后互动时间
        cursor.execute(
            """
            UPDATE follows 
            SET last_interaction_time = ?
            WHERE user_id = ?
            """,
            (now, user_id)
        )
        
        self.conn.commit()
        logger.info(f"已添加用户 {user_id} 的互动记录: {interaction_type}")
        return True
        
    except Exception as e:
        logger.error(f"添加互动记录失败: {str(e)}")
        return False
```

#### 5.3.4 check_follow_back

```python
def check_follow_back(self, user_id, username):
    """
    检查用户是否回关
    
    参数:
        user_id: 用户ID
        username: 用户名
        
    返回:
        bool: 是否回关
    """
    try:
        # 访问用户主页
        logger.info(f"访问用户主页检查回关状态: {username} ({user_id})")
        self.driver.get(f"https://www.douyin.com/user/{user_id}")
        self.random_sleep(3, 5)
        
        # 保存页面截图
        save_screenshot(self.driver, f"check_follow_back_{user_id}", level="DEBUG")
        
        # 查找互相关注标识
        mutual_follow_indicators = [
            "//span[contains(text(), '互相关注')]",
            "//div[contains(@class, 'mutual-relation')]",
            "//div[contains(text(), '互相关注')]"
        ]
        
        for indicator in mutual_follow_indicators:
            try:
                elements = self.driver.find_elements(By.XPATH, indicator)
                if elements and any(element.is_displayed() for element in elements):
                    logger.info(f"检测到用户 {username} ({user_id}) 已回关")
                    # 更新回关状态
                    self.update_follow_back_status(user_id, follow_back=1)
                    return True
            except:
                continue
        
        logger.info(f"用户 {username} ({user_id}) 未回关")
        # 更新回关状态
        self.update_follow_back_status(user_id, follow_back=0)
        return False
            
    except Exception as e:
        logger.error(f"检查回关状态失败: {str(e)}")
        return False
```

## 6. 配置参数

### 6.1 关注管理配置

```yaml
follow_management:
  enabled: true                  # 是否启用关注管理功能
  max_unfollow_per_day: 50       # 每天最多取消关注的用户数量
  unfollow_conditions:           # 取消关注条件
    min_follow_days: 7           # 最少关注天数
    min_follow_days_for_fans: 14 # 粉丝的最少关注天数
  check_follow_back:             # 检查回关配置
    enabled: true                # 是否启用检查回关功能
    check_interval_days: 3       # 检查间隔天数
  wait_time:                     # 等待时间配置
    between_users: [30, 60]      # 处理用户之间的等待时间范围（秒）
    after_unfollow: [3, 5]       # 取消关注后的等待时间范围（秒）
```

### 6.2 取消关注频率限制配置

```yaml
unfollow_rate_limit:
  max_per_hour: 20               # 每小时最多取消关注的用户数量
  max_retries: 3                 # 最大重试次数
  retry_interval_days: 1         # 重试间隔天数
```

## 7. 异常处理

### 7.1 常见异常

1. 网络连接异常
2. 页面元素未找到
3. 取消关注失败
4. 取消关注频率限制
5. 数据库操作异常

### 7.2 异常处理策略

1. 记录详细的错误日志
2. 对于网络异常，进行重试
3. 对于页面元素未找到，尝试不同的选择器
4. 对于取消关注失败，记录尝试次数并在下次重试
5. 对于数据库异常，回滚事务并记录错误

## 8. 日志记录

### 8.1 日志级别

1. INFO: 记录正常操作流程
2. WARNING: 记录可能的问题但不影响主要功能
3. ERROR: 记录导致功能失败的错误
4. DEBUG: 记录详细的调试信息

### 8.2 日志内容

1. 操作时间
2. 操作类型
3. 操作结果
4. 错误信息（如果有）
5. 相关数据（用户ID、取消关注原因等）

## 9. 性能优化

### 9.1 优化策略

1. 批量处理关注用户，减少浏览器启动次数
2. 使用数据库索引加速查询
3. 使用连接池管理数据库连接
4. 异步处理非关键操作
5. 定期清理历史数据，减少数据库大小 