"""
抖音网页版元素选择器配置
"""

# 用户主页元素
USER_PROFILE = {
    # 粉丝按钮
    'FANS_TAB': '//div[contains(@class, "tab-bar")]//div[text()="粉丝"]',
    # 关注按钮
    'FOLLOW_BTN': '//button[contains(@class, "follow") and not(contains(@class, "following"))]',
    # 已关注按钮
    'FOLLOWING_BTN': '//button[contains(@class, "following")]',
    # 粉丝列表
    'FANS_LIST': '//div[contains(@class, "user-list")]',
    # 粉丝项
    'FAN_ITEM': '//div[contains(@class, "user-item")]',
    # 用户名
    'USERNAME': './/span[contains(@class, "user-name")]',
    # 用户ID
    'USER_ID': './/span[contains(@class, "unique-id")]',
    # 关注列表按钮
    'FOLLOWING_TAB': '//div[contains(@class, "tab-bar")]//div[text()="关注"]',
    # 关注列表
    'FOLLOWING_LIST': '//div[contains(@class, "user-list")]',
    # 关注项
    'FOLLOWING_ITEM': '//div[contains(@class, "user-item")]',
    # 取消关注按钮
    'UNFOLLOW_BTN': '//button[contains(@class, "following")]',
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
} 