"""
私信管理模块

该模块提供了对粉丝进行私信互动的功能。
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import random
import time
from datetime import datetime, timedelta
from .logger import logger, save_screenshot
from utils.db import Database
from utils.config import load_config
from .browser import BrowserManager
from .message_utils import MessageUtils

class MessageManager:
    """私信管理器，负责处理粉丝私信互动"""
    
    def __init__(self, browser_manager: BrowserManager, db: Database, config: dict):
        """
        初始化私信管理器
        
        参数:
            browser_manager: 浏览器管理器对象
            db: 数据库对象
            config: 配置对象
        """
        self.browser = browser_manager
        self.db = db
        self.config = config
        self.driver = browser_manager.driver
        self.wait = browser_manager.wait
        self.random_sleep = browser_manager.random_sleep
        
        # 初始化消息工具类
        self.message_utils = MessageUtils(self.driver, self.wait, self.random_sleep, self.db)
        
        # 每日最大私信数量
        self.max_messages_per_day = config.get('operation', {}).get('fan_list_tasks', {}).get('max_messages_per_day', 100)
        
        # 每轮处理的粉丝数量
        self.batch_size = config.get('operation', {}).get('fan_list_tasks', {}).get('batch_size', 50)
        
        # 私信模板
        self.message_templates = {
            0: config.get('message_templates', {}).get('day_1', [
                "你好呀，很高兴认识你~",
                "Hi，我是{username}，谢谢你的关注！",
                "嗨，感谢关注，希望我们能成为好朋友~"
            ]),
            1: config.get('message_templates', {}).get('day_2', [
                "最近在忙什么呢？",
                "今天过得怎么样呀？",
                "有什么有趣的事情想分享吗？"
            ]),
            2: config.get('message_templates', {}).get('day_3', [
                "这几天聊得很开心，希望以后也能经常互动~",
                "感谢这几天的交流，你真的很有趣！",
                "和你聊天很愉快，期待更多的分享~"
            ])
        }

    def get_message_template(self, days_since_follow: int, username: str) -> str:
        """
        获取指定天数的消息模板
        
        参数:
            days_since_follow: 粉丝关注天数（0,1,2分别代表第一、二、三天）
            username: 用户名，用于替换模板中的变量
            
        返回:
            str: 消息模板内容，如果没有找到合适的模板则返回None
        """
        try:
            # 验证days_since_follow的值
            if not isinstance(days_since_follow, int) or days_since_follow not in [0, 1, 2]:
                logger.warning(f"无效的days_since_follow值: {days_since_follow}")
                return None
                
            # 获取消息模板配置
            message_templates = self.config.get('message_templates', {})
            if not message_templates:
                logger.error("配置文件中未找到消息模板")
                return None
                
            # 获取对应天数的模板列表
            template_key = f"day_{days_since_follow + 1}"  # 转换为day_1, day_2, day_3
            templates = message_templates.get(template_key, [])
            
            if not templates:
                logger.warning(f"未找到第 {days_since_follow + 1} 天的消息模板")
                return None
                
            # 随机选择一个模板
            message_template = random.choice(templates)
            
            # 返回格式化后的消息
            return message_template.format(username=username)
            
        except Exception as e:
            logger.error(f"获取消息模板失败: {str(e)}")
            return None

    def send_message(self, user_id: str, username: str, days_since_follow: int) -> bool:
        """
        发送私信给指定用户
        
        参数:
            user_id: 用户ID
            username: 用户名
            days_since_follow: 粉丝关注天数（0,1,2分别代表第一、二、三天）
            
        返回:
            bool: 是否成功发送
        """
        try:
            # 获取对应天数的消息模板
            message = self.get_message_template(days_since_follow, username)
            if not message:
                logger.error(f"无法获取第 {days_since_follow + 1} 天的消息模板")
                return False
            
            # 使用共通方法发送私信
            return self.message_utils.send_message(user_id, username, message, days_since_follow)
            
        except Exception as e:
            logger.error(f"发送私信失败: {str(e)}")
            save_screenshot(self.driver, f"send_message_error_{user_id}")
            return False
    
    def run_fan_message_task(self) -> bool:
        """
        运行粉丝私信任务
        
        功能：
        1. 检查今日私信数量是否达到上限
        2. 获取需要发送私信的粉丝
        3. 根据关注天数发送不同的私信
        
        返回:
            bool: 任务执行成功返回True，否则返回False
        """
        try:
            logger.info("开始执行粉丝私信任务...")
            
            # 检查今日私信数量是否达到上限
            today_count = self.db.get_today_message_count()
            if today_count >= self.max_messages_per_day:
                logger.info(f"今日私信数量已达上限: {today_count}/{self.max_messages_per_day}")
                return True
                
            # 获取需要发送私信的粉丝
            remaining = self.max_messages_per_day - today_count
            batch_size = min(remaining, self.batch_size)
            fans = self.db.get_fans_need_message(limit=batch_size)
            
            if not fans:
                logger.info("没有需要发送私信的粉丝")
                return True
                
            logger.info(f"开始处理 {len(fans)} 个粉丝的私信任务")
            success_count = 0
            
            for fan in fans:
                try:
                    user_id = fan['user_id']
                    username = fan['username']
                    days_since_follow = fan['days_since_follow']
                    
                    # 发送私信
                    if self.send_message(user_id, username, days_since_follow):
                        success_count += 1
                        # 更新粉丝互动状态
                        self.db.update_fan_interaction(user_id)
                        logger.info(f"完成与粉丝 {username} 的第 {days_since_follow + 1} 天互动")
                    
                    # 随机延迟，避免操作过快
                    time.sleep(random.uniform(2, 5))
                    
                except Exception as e:
                    logger.error(f"处理粉丝 {fan.get('username', 'unknown')} 的互动任务失败: {str(e)}")
                    continue
            
            logger.info(f"完成粉丝私信任务，成功发送 {success_count}/{len(fans)} 条私信")
            return True
            
        except Exception as e:
            logger.error(f"运行粉丝私信任务失败: {str(e)}")
            return False 