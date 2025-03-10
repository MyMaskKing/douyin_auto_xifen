"""
抖音网页版元素选择器配置
"""

# 用户主页元素
USER_PROFILE = {
    # 粉丝按钮 - 更新为更精确的选择器
    'FANS_TAB': [
        # 最常见的粉丝标签选择器
        '//div[contains(@class, "tab-bar")]//div[text()="粉丝"]',
        '//div[contains(@class, "tab-container")]//div[text()="粉丝"]',
        '//span[text()="粉丝"]',
        '//div[contains(@class, "count-item") and contains(., "粉丝")]',
        
        # 抖音特定选择器
        '//div[contains(@class, "author-card")]//div[contains(text(), "粉丝")]',
        '//div[contains(@class, "count-item") and .//span[contains(text(), "粉丝")]]',
        '//div[contains(@class, "tab-item") and .//span[contains(text(), "粉丝")]]',
        '//div[contains(@class, "tab-item") and contains(., "粉丝")]',
        
        # 通用选择器
        '//div[contains(text(), "粉丝")]',
        '//span[contains(text(), "粉丝")]',
        '//a[contains(text(), "粉丝")]',
        
        # 带数字的粉丝标签
        '//div[contains(text(), "粉丝") and contains(text(), "万") or contains(text(), "亿") or contains(text(), "0") or contains(text(), "1") or contains(text(), "2") or contains(text(), "3") or contains(text(), "4") or contains(text(), "5") or contains(text(), "6") or contains(text(), "7") or contains(text(), "8") or contains(text(), "9")]',
        '//span[contains(text(), "粉丝") and contains(text(), "万") or contains(text(), "亿") or contains(text(), "0") or contains(text(), "1") or contains(text(), "2") or contains(text(), "3") or contains(text(), "4") or contains(text(), "5") or contains(text(), "6") or contains(text(), "7") or contains(text(), "8") or contains(text(), "9")]'
    ],
    # 关注按钮 - 更新为最新的选择器
    'FOLLOW_BTN': [
        # 新版抖音关注按钮选择器
        '//div[contains(@class, "Q1A_pjwq") and contains(@class, "ELUP9h2u") and @data-e2e="user-info-follow"]',
        '//div[@data-e2e="user-info-follow"]',
        # 旧版选择器保留作为备用
        '//button[contains(@class, "follow") and not(contains(@class, "following"))]',
    ],
    # 已关注按钮
    'FOLLOWING_BTN': [
        '//div[contains(@class, "Q1A_pjwq") and contains(@class, "ELUP9h2u") and @data-e2e="user-info-following"]',
        '//div[@data-e2e="user-info-following"]',
        '//button[contains(@class, "following")]'
    ],
    # 关注状态文本
    'FOLLOW_STATUS_TEXT': '//div[contains(@class, "uvGnYXqn") and text()="关注"]',
    # 粉丝列表
    'FANS_LIST': '//div[contains(@class, "user-list")]',
    # 粉丝项
    'FAN_ITEM': '//div[contains(@class, "user-item")]',
    # 用户名
    'USERNAME': './/span[contains(@class, "user-name")]',
    # 用户ID
    'USER_ID': './/span[contains(@class, "unique-id")]',
    # 关注列表按钮
    'FOLLOWING_TAB': [
        '//div[contains(@class, "tab-bar")]//div[text()="关注"]',
        '//div[contains(@text(), "关注") and not(contains(@text(), "粉丝"))]'
    ],
    # 关注列表
    'FOLLOWING_LIST': '//div[contains(@class, "user-list")]',
    # 关注项
    'FOLLOWING_ITEM': '//div[contains(@class, "user-item")]',
    # 取消关注按钮
    'UNFOLLOW_BTN': [
        '//div[contains(@class, "Q1A_pjwq") and contains(@class, "ELUP9h2u") and @data-e2e="user-info-following"]',
        '//button[contains(@class, "following")]'
    ],
    # 确认取消关注按钮
    'CONFIRM_UNFOLLOW_BTN': '//button[contains(text(), "取消关注")]',
}

# 通用元素
COMMON = {
    # 加载提示
    'LOADING': '//div[contains(@class, "loading")]',
    # 登录状态检查 - 多种可能的元素
    'LOGIN_CHECK': [
        '//span[contains(@class, "login-name")]',  # 用户名显示
        '//div[contains(@class, "avatar")]',       # 头像元素
        '//button[contains(text(), "发布")]',       # 发布按钮
        '//div[contains(@class, "user-info")]',    # 用户信息区域
        '//div[contains(@class, "personal-tab")]', # 个人标签页
        '//div[contains(@class, "im")]',           # 消息图标
        '//div[contains(@class, "notice")]'        # 通知图标
    ],
    # 个人主页链接 - 用于检查登录状态
    'PROFILE_LINK': [
        '//div[contains(@class, "avatar")]',       # 头像元素通常可以点击进入个人主页
        '//span[contains(@class, "login-name")]',  # 用户名通常可以点击进入个人主页
        '//div[contains(@class, "user-info")]',    # 用户信息区域通常可以点击进入个人主页
        '//a[contains(@href, "/user/")]'           # 指向用户主页的链接
    ],
    # 个人主页信息元素 - 用于验证是否成功进入个人主页
    'PROFILE_INFO': [
        '//div[contains(@class, "author-card")]',  # 作者卡片
        '//div[contains(@class, "user-info")]',    # 用户信息区域
        '//div[contains(@class, "personal-tab")]', # 个人标签页
        '//div[contains(@class, "count-item")]',   # 计数项（粉丝数、关注数等）
        '//div[contains(@class, "tab-bar")]'       # 标签栏
    ],
} 