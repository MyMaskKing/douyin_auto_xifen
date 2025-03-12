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
from selenium.webdriver.common.action_chains import ActionChains

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
        
        # 每日最大私信数量
        self.max_messages_per_day = config.get('operation', {}).get('message', {}).get('max_messages_per_day', 100)
        
        # 每轮处理的粉丝数量
        self.batch_size = config.get('operation', {}).get('message', {}).get('batch_size', 50)
        
        # 私信模板
        self.message_templates = {
            0: config.get('operation', {}).get('message', {}).get('templates', {}).get('day1', [
                "你好呀，很高兴认识你~",
                "Hi，我是{username}，谢谢你的关注！",
                "嗨，感谢关注，希望我们能成为好朋友~"
            ]),
            1: config.get('operation', {}).get('message', {}).get('templates', {}).get('day2', [
                "最近在忙什么呢？",
                "今天过得怎么样呀？",
                "有什么有趣的事情想分享吗？"
            ]),
            2: config.get('operation', {}).get('message', {}).get('templates', {}).get('day3', [
                "这几天聊得很开心，希望以后也能经常互动~",
                "感谢这几天的交流，你真的很有趣！",
                "和你聊天很愉快，期待更多的分享~"
            ])
        }

    def get_message_template(self, days_followed: int, username: str) -> str:
        """根据关注天数获取消息模板"""
        if days_followed not in self.message_templates:
            return ""
            
        templates = self.message_templates[days_followed]
        message = random.choice(templates)
        return message.format(username=username)
    
    def send_message(self, user_id: str, username: str, days_followed: int) -> bool:
        """
        发送私信给指定用户
        
        参数:
            user_id: 用户ID
            username: 用户名
            days_followed: 已关注天数，用于选择对应的消息模板
            
        返回:
            bool: 发送成功返回True，否则返回False
        """
        try:
            # 获取消息模板
            message = self.get_message_template(days_followed, username)
            if not message:
                logger.warning(f"未找到适合的消息模板: {user_id}, days_followed={days_followed}")
                return False
                
            # 访问用户主页
            logger.info(f"访问用户主页准备发送私信: {username} ({user_id})")
            self.driver.get(f"https://www.douyin.com/user/{user_id}")
            self.random_sleep(3, 5)
            
            # 保存页面截图
            save_screenshot(self.driver, f"send_message_{user_id}", level="NORMAL")
            
            # 查找私信按钮
            message_button = None
            message_button_selectors = [
                "//button[contains(@class, 'semi-button-secondary') and contains(@class, 'semi-button')]//span[text()='私信']/parent::button",
                "//button[contains(@class, 'K8kpIsJm')][.//span[text()='私信']]",
                "//button[contains(@class, 'semi-button-secondary')][.//span[text()='私信']]",
                "//button[contains(@class, 'semi-button')]//span[text()='私信']/parent::button"
            ]
            
            for selector in message_button_selectors:
                try:
                    message_button = self.driver.find_element(By.XPATH, selector)
                    logger.info(f"找到私信按钮: {selector}")
                    break
                except:
                    continue
            
            if not message_button:
                logger.warning(f"未找到私信按钮: {username} ({user_id})")
                return False
            
            # 点击私信按钮
            logger.info(f"点击私信按钮: {username} ({user_id})")
            try:
                message_button.click()
                self.random_sleep(2, 3)
            except:
                # 尝试使用JavaScript点击
                try:
                    self.driver.execute_script("arguments[0].click();", message_button)
                    self.random_sleep(2, 3)
                except Exception as e:
                    logger.error(f"点击私信按钮失败: {str(e)}")
                    return False
            
            # 查找私信输入框
            message_input = None
            message_input_selectors = [
                "//div[contains(@class, 'public-DraftEditor-content')]",
                "//div[contains(@class, 'DraftEditor-editorContainer')]//div[@contenteditable='true']",
                "//div[contains(@class, 'im-richtext-container')]//div[@contenteditable='true']"
            ]
            
            for selector in message_input_selectors:
                try:
                    message_input = self.driver.find_element(By.XPATH, selector)
                    logger.info(f"找到私信输入框: {selector}")
                    break
                except:
                    continue
            
            if not message_input:
                logger.warning(f"未找到私信输入框: {username} ({user_id})")
                return False
                
            # 输入私信内容
            logger.info(f"输入私信内容: {message}")
            try:
                # 先点击输入框激活它
                message_input.click()
                self.random_sleep(1, 2)
                
                # 清空输入框
                message_input.clear()
                self.random_sleep(0.5, 1)
                
                # 模拟人工输入
                for char in message:
                    message_input.send_keys(char)
                    # 随机等待一个很短的时间，模拟人工输入速度
                    time.sleep(random.uniform(0.1, 0.3))
                
                self.random_sleep(1, 2)
            except Exception as e:
                logger.error(f"输入私信内容失败: {str(e)}")
                return False
                
            # 查找发送按钮
            send_button = None
            send_button_selectors = [
                "//span[contains(@class, 'PygT7Ced') and contains(@class, 'JnY63Rbk') and contains(@class, 'e2e-send-msg-btn')]",
                "//span[contains(@class, 'PygT7Ced')]//svg",
                "//span[contains(@class, 'e2e-send-msg-btn')]"
            ]
            
            for selector in send_button_selectors:
                try:
                    send_button = self.driver.find_element(By.XPATH, selector)
                    logger.info(f"找到发送按钮: {selector}")
                    break
                except:
                    continue
            
            if send_button:
                # 点击发送按钮
                logger.info("点击发送按钮")
                try:
                    # 尝试直接点击
                    send_button.click()
                    self.random_sleep(2, 3)
                except:
                    try:
                        # 如果直接点击失败，尝试点击父元素
                        parent = send_button.find_element(By.XPATH, "..")
                        parent.click()
                        self.random_sleep(2, 3)
                    except:
                        # 如果点击父元素也失败，尝试使用JavaScript点击
                        try:
                            self.driver.execute_script("arguments[0].click();", send_button)
                            self.random_sleep(2, 3)
                        except Exception as e:
                            logger.error(f"点击发送按钮失败: {str(e)}")
                            return False
            else:
                # 如果没有找到发送按钮，尝试按回车键发送
                logger.info("未找到发送按钮，尝试按回车键发送")
                message_input.send_keys(Keys.ENTER)
                self.random_sleep(2, 3)
            
            # 检查是否发送成功
            try:
                # 等待发送按钮变为灰色状态（JnY63Rbk类名消失）
                self.wait.until(lambda d: len(d.find_elements(By.XPATH, "//span[contains(@class, 'PygT7Ced') and contains(@class, 'e2e-send-msg-btn') and not(contains(@class, 'JnY63Rbk'))]")) > 0)
                logger.info(f"成功发送私信给用户: {username} ({user_id})")
                
                # 记录私信历史
                self.db.add_message_record(user_id, message)
                
                return True
            except Exception as e:
                logger.warning(f"无法确认私信是否发送成功: {str(e)}")
                # 再次检查按钮状态
                try:
                    time.sleep(2)
                    # 如果找到了灰色状态的按钮，说明发送成功
                    if len(self.driver.find_elements(By.XPATH, "//span[contains(@class, 'PygT7Ced') and contains(@class, 'e2e-send-msg-btn') and not(contains(@class, 'JnY63Rbk'))]")) > 0:
                        logger.info(f"通过按钮状态确认私信发送成功: {username} ({user_id})")
                        
                        # 记录私信历史
                        self.db.add_message_record(user_id, message)
                        
                        return True
                except:
                    pass
                return False
                
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
                    days_followed = fan['days_followed']
                    
                    # 发送私信
                    if self.send_message(user_id, username, days_followed):
                        success_count += 1
                        # 更新粉丝互动状态
                        self.db.update_fan_interaction(user_id, days_followed + 1)
                        logger.info(f"完成与粉丝 {username} 的第 {days_followed + 1} 天互动")
                    
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