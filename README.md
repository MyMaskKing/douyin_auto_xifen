# 抖音自动涨粉工具

这是一个基于Edge浏览器的抖音自动涨粉工具，通过模拟真实用户操作来增加粉丝数量。工具设计简单易用，专注于核心功能。

## 功能特点

- 自动关注目标用户的粉丝
- 自动取关超过指定天数未回关的用户
- 保存浏览器登录状态，无需重复登录
- 支持工作时间设置，避免异常操作时间
- 关闭浏览器窗口时自动退出程序

## 环境要求

- Python 3.9+
- Edge浏览器
- Windows系统

## 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/yourusername/douyin_auto_xifen.git
cd douyin_auto_xifen
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置设置
```bash
cp config/config.example.yaml config/config.yaml
# 编辑config.yaml文件，设置目标用户和操作参数
```

## 使用方法

1. 运行程序
```bash
python main.py
```

2. 首次运行时，在弹出的浏览器中登录抖音
3. 登录后按回车键继续
4. 程序会自动开始关注目标用户的粉丝
5. 关闭浏览器窗口可以随时停止程序

## 配置说明

在`config/config.yaml`文件中：

```yaml
# 目标配置
target:
  users:  # 目标用户列表（想要涨粉的同类型账号）
    - "user1"  # 替换为实际的抖音用户ID
    - "user2"  # 替换为实际的抖音用户ID
  
# 操作配置
operation:
  daily_follow_limit: 150  # 每日关注上限
  daily_unfollow_limit: 100  # 每日取关上限
  follow_interval: [30, 60]  # 关注操作间隔（秒）
  unfollow_interval: [20, 40]  # 取关操作间隔（秒）
  unfollow_days: 3  # 超过几天未回关则取关
  
# 工作时间配置
working_hours:
  # 方式1：配置为空列表，表示全天运行
  # []
  
  # 方式2：配置[0, 24]，表示全天运行
  # - [0, 24]
  
  # 方式3：配置具体的时间段（默认）
  - [9, 12]  # 上午9点到12点
  - [14, 17]  # 下午2点到5点
  - [19, 22]  # 晚上7点到10点
```

## 注意事项

- 本工具仅供学习和研究使用
- 请遵守抖音平台的使用条款和规则
- 过度使用可能导致账号被限制或封禁
- 请合理设置操作频率和使用时长

## 许可证

MIT License