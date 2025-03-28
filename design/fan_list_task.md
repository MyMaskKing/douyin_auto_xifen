# 粉丝列表相关任务设计文档

## 1. 概述

本文档详细描述抖音自动化工具中与粉丝列表管理相关的任务设计，包括粉丝数据管理、私信发送、粉丝互动等功能。

## 2. 数据库设计

### 2.1 粉丝记录表 (fans)

| 字段名 | 类型 | 说明 |
|-------|------|------|
| user_id | TEXT | 用户ID，主键 |
| username | TEXT | 用户名 |
| first_seen_time | TIMESTAMP | 首次发现时间 |
| last_seen_time | TIMESTAMP | 最后一次发现时间 |
| follow_status | TEXT | 关注状态（new_fan/need_follow_back/mutual/requested） |
| is_processed | INTEGER | 是否已处理，0表示未处理，1表示已处理 |
| need_follow_back | INTEGER | 是否需要回关，0表示不需要，1表示需要 |
| follow_back_time | TIMESTAMP | 回关时间 |
| days_followed | INTEGER | 已关注天数 |
| last_message_time | TIMESTAMP | 最后一次私信时间 |
| message_count | INTEGER | 私信次数 |
| is_valid_fan | INTEGER | 是否是有效粉丝，0表示否，1表示是 |
| message_retry_count | INTEGER | 私信重试次数 |
| last_message_retry_time | TIMESTAMP | 最后一次私信重试时间 |
| message_fail_reason | TEXT | 私信失败原因 |

### 2.2 私信记录表 (messages)

| 字段名 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 自增主键 |
| user_id | TEXT | 用户ID，外键关联fans表 |
| message | TEXT | 私信内容 |
| send_time | TIMESTAMP | 发送时间 |

### 2.3 待关注粉丝表 (follow_fans)

| 字段名 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 自增主键 |
| user_id | TEXT | 用户ID |
| username | TEXT | 用户名 |
| from_type | TEXT | 粉丝来源类型（video_comment, video_like等） |
| source_id | TEXT | 来源ID，如视频ID |
| created_at | TIMESTAMP | 创建时间 |
| processed | INTEGER | 是否已处理，0表示未处理，1表示已处理 |

## 3. 粉丝数据管理功能

### 3.1 功能描述

该功能负责管理粉丝数据，包括添加新粉丝、更新粉丝状态、获取粉丝列表等。

### 3.2 处理流程

```
开始
  |
  v
检查用户是否已在粉丝表中 --> 存在 --> 更新粉丝记录
  |
  v (不存在)
添加新粉丝记录
  |
  v
设置粉丝状态和属性
  |
  v
提交数据库事务
  |
  v
结束
```

### 3.3 主要方法

#### 3.3.1 add_fan_record

该方法用于添加新的粉丝记录：

1. 接收用户ID、用户名和关注状态作为参数，返回布尔值表示操作是否成功
2. 获取当前时间戳，用于记录首次和最后一次发现时间
3. 使用SQLite数据库连接对象获取游标
4. 检查用户是否已在粉丝表中
   - 执行SELECT查询，获取用户ID、关注状态和首次发现时间
   - 如果用户已存在，更新粉丝记录：
     - 更新last_seen_time为当前时间
     - 更新follow_status为新的状态
     - 如果新状态为"need_follow_back"，设置need_follow_back为1
   - 如果用户不存在，插入新的粉丝记录：
     - 设置user_id、username、first_seen_time、last_seen_time等基本字段
     - 设置follow_status为指定状态
     - 设置need_follow_back根据状态决定（如果状态为"need_follow_back"则为1，否则为0）
     - 初始化days_followed、is_processed和is_valid_fan为0
5. 提交数据库事务，确保数据持久化
6. 使用logger记录操作成功信息，包含用户名、用户ID和状态
7. 返回True表示操作成功
8. 使用try-except结构捕获可能的数据库异常
9. 异常发生时，使用logger记录错误信息并返回False
10. 该方法确保系统能够准确记录粉丝数据，便于后续分析和管理

#### 3.3.2 get_user_by_id

该方法用于根据用户ID获取用户信息：

1. 接收用户ID作为参数，返回包含用户信息的字典或None
2. 使用SQLite数据库连接对象获取游标
3. 执行SELECT查询，从fans表中获取指定用户ID的所有字段
4. 如果查询结果存在：
   - 获取查询结果的列名
   - 将查询结果转换为字典，键为列名，值为对应的字段值
   - 返回包含用户信息的字典
5. 如果查询结果不存在，返回None
6. 使用try-except结构捕获可能的数据库异常
7. 异常发生时，使用logger记录错误信息并返回None
8. 该方法帮助系统快速获取特定用户的完整信息，便于后续处理

#### 3.3.3 update_fan_interaction

该方法用于更新粉丝互动状态：

1. 接收用户ID作为参数，返回布尔值表示操作是否成功
2. 获取当前时间戳，用于计算时间差
3. 使用SQLite数据库连接对象获取游标
4. 计算用户关注天数：
   - 执行SQL查询，使用julianday函数计算当前日期与first_seen_time之间的天数差
   - 使用CAST函数将结果转换为整数
5. 更新粉丝状态：
   - 设置days_followed为计算得到的天数差
   - 设置is_valid_fan字段：如果关注天数大于等于3天，则设为1（有效粉丝），否则设为0
6. 提交数据库事务，确保数据持久化
7. 返回True表示操作成功
8. 使用try-except结构捕获可能的数据库异常
9. 异常发生时，使用logger记录错误信息并返回False
10. 该方法帮助系统追踪粉丝互动状态，识别长期关注的有效粉丝

## 4. 私信发送功能

### 4.1 功能描述

该功能负责向粉丝发送私信，包括获取需要发送私信的粉丝、生成私信内容、发送私信、记录私信状态等。

### 4.2 处理流程

```
开始
  |
  v
获取需要发送私信的粉丝列表
  |
  v
循环处理每个粉丝 --> 粉丝列表为空 --> 结束
  |
  v (有粉丝)
检查私信频率限制 --> 超过限制 --> 跳过当前粉丝
  |
  v (未超过限制)
生成私信内容
  |
  v
发送私信
  |
  v
检查发送结果 --> 失败 --> 记录失败原因和重试信息
  |
  v (成功)
更新私信记录
  |
  v
继续处理下一个粉丝
```

### 4.3 主要方法

#### 4.3.1 get_fans_need_message

该方法用于获取需要发送私信的粉丝：

1. 接收可选参数limit，表示最大返回数量
2. 获取当前时间戳，用于计算时间差
3. 使用SQLite数据库连接对象获取游标
4. 执行SELECT查询，从fans表中获取满足以下条件的粉丝：
   - 关注天数不超过2天（处理前三天的粉丝，包括第0、1、2天）
   - 从未发送过私信（last_message_time为NULL）或今天还没有发送过私信且距离上次私信至少1天
   - 按first_seen_time字段升序排序（优先处理较早的粉丝）
   - 限制返回数量为指定的limit值
5. 获取查询结果的列名和数据行
6. 将结果转换为字典列表，每个字典包含user_id、username和days_since_follow等信息
7. 返回粉丝字典列表
8. 使用try-except结构捕获可能的数据库异常
9. 异常发生时，使用logger记录错误信息并返回空列表
10. 该方法帮助系统高效地识别需要发送私信的粉丝，便于批量处理

#### 4.3.2 add_message_record

该方法用于添加私信记录：

1. 接收用户ID和私信内容作为参数，返回布尔值表示操作是否成功
2. 获取当前时间戳，用于记录发送时间
3. 使用SQLite数据库连接对象获取游标
4. 执行两个数据库操作：
   - 在messages表中插入新的私信记录，包含用户ID、私信内容和发送时间
   - 更新fans表中的私信相关字段，包括last_message_time和message_count
5. 提交数据库事务，确保数据持久化
6. 返回True表示操作成功
7. 使用try-except结构捕获可能的数据库异常
8. 异常发生时，使用logger记录错误信息并返回False
9. 该方法确保系统能够准确记录私信历史，便于后续分析和管理

#### 4.3.3 send_message

该方法用于向指定用户发送私信：

1. 接收用户ID、用户名和私信内容作为参数，返回布尔值表示操作是否成功
2. 使用Selenium WebDriver访问用户主页
   - 构建用户主页URL并使用get方法打开
   - 使用随机等待函数模拟人类操作的随机性
   - 保存页面截图用于记录和调试
3. 查找私信按钮
   - 使用多个XPath选择器尝试定位私信按钮元素
   - 检查元素是否可见和可点击
   - 如果未找到私信按钮，记录日志并返回False
4. 点击私信按钮
   - 使用click方法或JavaScript执行点击操作
   - 使用随机等待函数模拟人类操作
   - 如果点击失败，记录日志并返回False
5. 查找私信输入框
   - 使用多个XPath选择器尝试定位输入框元素
   - 如果未找到输入框，记录日志并返回False
6. 输入私信内容
   - 点击输入框并清空内容
   - 逐字符输入私信内容，模拟人类打字行为
   - 使用随机等待函数模拟人类操作
   - 如果输入失败，记录日志并返回False
7. 查找并点击发送按钮
   - 使用多个XPath选择器尝试定位发送按钮
   - 如果找到发送按钮，使用click方法或JavaScript执行点击操作
   - 如果未找到发送按钮，尝试使用回车键发送
   - 使用随机等待函数模拟人类操作
8. 检查发送结果
   - 使用WebDriverWait等待发送按钮状态变化
   - 检查页面是否出现"消息发送太频繁"的提示
   - 如果出现频率限制，实现重试机制：
     - 记录重试次数，最多重试3次
     - 每次重试前等待5分钟
     - 如果连续3次都失败，记录日志并返回False
   - 如果发送成功，记录日志并返回True
9. 使用try-except结构捕获可能的异常
10. 异常发生时，使用logger记录错误信息并返回False
11. 该方法实现了完整的私信发送流程，包括页面交互、异常处理和重试机制

## 5. 粉丝互动功能

### 5.1 功能描述

该功能负责与粉丝进行互动，包括标记粉丝为待回关、回关粉丝等。

### 5.2 处理流程

```
开始
  |
  v
获取需要回关的粉丝列表
  |
  v
循环处理每个粉丝 --> 粉丝列表为空 --> 结束
  |
  v (有粉丝)
访问粉丝主页
  |
  v
点击关注按钮
  |
  v
检查关注结果 --> 失败 --> 记录失败原因
  |
  v (成功)
标记粉丝为已回关
  |
  v
继续处理下一个粉丝
```

### 5.3 主要方法

#### 5.3.1 mark_user_for_follow_back

该方法用于将用户标记为待回关：

1. 接收用户ID和用户名作为参数，返回布尔值表示操作是否成功
2. 获取当前时间戳，用于记录标记时间
3. 使用SQLite数据库连接对象获取游标
4. 检查用户是否已在粉丝表中
   - 执行SELECT查询，获取用户的关注状态和回关标记
   - 如果用户已存在且已被标记为待回关，记录日志并返回True
5. 根据用户是否存在执行不同的操作：
   - 如果用户存在，更新用户状态为"need_follow_back"，设置need_follow_back为1
   - 如果用户不存在，插入新的粉丝记录，设置适当的初始值
6. 提交数据库事务，确保数据持久化
7. 使用logger记录操作成功信息
8. 返回True表示操作成功
9. 使用try-except结构捕获可能的数据库异常
10. 异常发生时，使用logger记录错误信息并返回False
11. 该方法确保系统能够追踪需要回关的粉丝，便于后续处理

#### 5.3.2 get_users_to_follow_back

该方法用于获取需要回关的用户列表：

1. 接收可选参数limit，表示最大返回数量
2. 使用SQLite数据库连接对象获取游标
3. 执行SELECT查询，从fans表中获取满足以下条件的用户：
   - need_follow_back字段为1（表示需要回关）
   - follow_back_time字段为NULL（表示尚未回关）
   - 按first_seen_time字段升序排序（优先处理较早的粉丝）
   - 限制返回数量为指定的limit值
4. 将查询结果转换为字典列表，每个字典包含user_id和username
5. 返回用户字典列表
6. 使用try-except结构捕获可能的数据库异常
7. 异常发生时，使用logger记录错误信息并返回空列表
8. 该方法帮助系统高效地识别需要回关的粉丝，便于批量处理

#### 5.3.3 mark_user_followed_back

该方法用于标记用户已回关：

1. 接收用户ID作为参数，返回布尔值表示操作是否成功
2. 获取当前时间戳，用于记录回关时间
3. 使用SQLite数据库连接对象获取游标
4. 执行两个数据库操作：
   - 更新fans表中的用户记录：设置follow_status为'followed_back'，need_follow_back为0，记录follow_back_time，标记is_processed为1
   - 在follows表中插入或更新关注记录：设置用户ID、用户名、关注时间和is_following状态
5. 提交数据库事务，确保数据持久化
6. 使用logger记录操作成功信息
7. 返回True表示操作成功
8. 使用try-except结构捕获可能的数据库异常
9. 异常发生时，使用logger记录错误信息并返回False
10. 该方法确保系统能够准确记录粉丝回关状态，维护粉丝关系数据的一致性

## 6. 配置参数

### 6.1 粉丝互动配置

```yaml
fan_interaction:
  enabled: true                  # 是否启用粉丝互动功能
  max_follow_back_per_day: 50    # 每天最多回关的粉丝数量
  max_messages_per_day: 100      # 每天最多发送的私信数量
  message_templates:             # 私信模板列表
    day0:                        # 第一天的私信模板
      - "你好，感谢关注！"
      - "谢谢你的关注，有什么问题可以随时私信我哦！"
    day1:                        # 第二天的私信模板
      - "今天过得怎么样？有什么我能帮到你的吗？"
      - "希望你今天过得愉快！"
    day2:                        # 第三天的私信模板
      - "已经是第三天了，感谢你的持续关注！"
      - "三天了，我们已经是好朋友了！"
  wait_time:                     # 等待时间配置
    between_users: [30, 60]      # 处理用户之间的等待时间范围（秒）
    after_message: [3, 5]        # 发送私信后的等待时间范围（秒）
```

### 6.2 私信频率限制配置

```yaml
message_rate_limit:
  retry_wait_time: 300           # 遇到频率限制时的等待时间（秒）
  max_retries: 3                 # 最大重试次数
  daily_limit: 100               # 每日私信上限
```

## 7. 异常处理

### 7.1 常见异常

1. 网络连接异常
2. 页面元素未找到
3. 私信发送失败
4. 私信频率限制
5. 数据库操作异常

### 7.2 异常处理策略

1. 记录详细的错误日志
2. 对于网络异常，进行重试
3. 对于页面元素未找到，尝试不同的选择器
4. 对于私信频率限制，等待一段时间后重试
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
5. 相关数据（用户ID、私信内容等）

## 9. 性能优化

### 9.1 优化策略

1. 批量处理粉丝，减少浏览器启动次数
2. 使用数据库索引加速查询
3. 使用连接池管理数据库连接
4. 异步处理非关键操作
5. 定期清理历史数据，减少数据库大小 