"""
关注管理模块

该模块提供了关注和取消关注用户的功能。
"""

from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    NoSuchElementException
)
import time
import random
import sys
from .logger import logger, save_screenshot, save_html

class FollowManager:
    """关注管理类，负责关注和取消关注用户"""
    
    def __init__(self, browser_manager, db):
        """
        初始化关注管理器
        
        参数:
            browser_manager: 浏览器管理器对象
            db: 数据库对象
        """
        self.browser_manager = browser_manager
        self.db = db
        self.driver = browser_manager.driver
        self.wait = browser_manager.wait
        self.random_sleep = browser_manager.random_sleep
        
    def follow_user(self, fan_item):
        """
        关注用户
        
        参数:
            fan_item: 粉丝项，包含元素、按钮和名称
            
        返回:
            成功返回True，失败返回False
        """
        try:
            # 检查fan_item是否是字典类型（新格式）
            if isinstance(fan_item, dict) and "button" in fan_item:
                # 直接使用字典中的按钮
                follow_btn = fan_item["button"]
                
                # 尝试提取用户信息
                try:
                    parent_element = fan_item["element"]
                    # 尝试查找用户名元素
                    name_elements = parent_element.find_elements(By.XPATH, 
                        ".//span[contains(@class, 'name') or contains(@class, 'nickname')] | .//div[contains(@class, 'name') or contains(@class, 'nickname')]")
                    
                    username = "未知用户"
                    if name_elements:
                        username = name_elements[0].text
                        
                    # 尝试查找用户ID元素
                    id_elements = parent_element.find_elements(By.XPATH, 
                        ".//span[contains(@class, 'id') or contains(@class, 'unique')] | .//div[contains(@class, 'id') or contains(@class, 'unique')]")
                    
                    user_id = None
                    if id_elements:
                        user_id = id_elements[0].text
                        # 有时候用户ID会带有@前缀，需要去掉
                        if user_id and user_id.startswith('@'):
                            user_id = user_id[1:]
                    
                    # 如果没有找到用户ID，使用时间戳作为临时ID
                    if not user_id:
                        user_id = f"temp_{int(time.time())}_{random.randint(1000, 9999)}"
                        
                    logger.info(f"准备关注用户: {username} ({user_id})")
                except Exception as e:
                    logger.error(f"提取用户信息失败: {str(e)}")
                    # 保存错误截图
                    save_screenshot(self.driver, "error", level="ERROR")
                    # 使用默认值
                    username = "未知用户"
                    user_id = f"temp_{int(time.time())}_{random.randint(1000, 9999)}"
                
                # 检查是否已经关注过
                try:
                    if self.db.is_followed(user_id):
                        logger.info(f"已经关注过用户: {username} ({user_id})")
                        return False
                except Exception as e:
                    logger.warning(f"检查用户关注状态失败: {str(e)}")
                
                # 检查按钮状态
                try:
                    # 检查按钮是否可见
                    if not follow_btn.is_displayed():
                        logger.warning(f"关注按钮不可见: {username}")
                        return False
                    
                    # 检查按钮文本
                    button_text = follow_btn.text
                    button_class = follow_btn.get_attribute("class")
                    button_data_e2e = follow_btn.get_attribute("data-e2e")
                    
                    logger.info(f"关注按钮信息: 文本='{button_text}', 类名='{button_class}', data-e2e='{button_data_e2e}'")
                    
                    # 检查是否已经关注
                    if button_text and ("已关注" in button_text or "互相关注" in button_text):
                        logger.info(f"用户已经被关注: {username}")
                        # 更新数据库
                        self.db.add_follow_record(user_id, username)
                        return False
                except Exception as e:
                    logger.warning(f"检查按钮状态失败: {str(e)}")
                
                # 保存关注前的截图
                save_screenshot(self.driver, "before_follow", level="NORMAL", user_id=user_id)
                
                # 尝试点击关注按钮
                try:
                    # 滚动到按钮位置
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", follow_btn)
                    self.random_sleep(1, 2)
                    
                    # 点击按钮
                    follow_btn.click()
                    logger.info(f"成功点击关注按钮: {username}")
                    self.random_sleep(1, 2)
                except ElementClickInterceptedException:
                    # 如果常规点击失败，尝试JavaScript点击
                    logger.info(f"常规点击失败，尝试JavaScript点击: {username}")
                    self.driver.execute_script("arguments[0].click();", follow_btn)
                    self.random_sleep(1, 2)
                except Exception as e:
                    logger.error(f"点击关注按钮失败: {str(e)}")
                    # 保存错误截图
                    save_screenshot(self.driver, "error", level="ERROR", user_id=user_id)
                    return False
                
                # 保存关注后的截图
                save_screenshot(self.driver, "after_follow", level="NORMAL", user_id=user_id)
                
                # 更新数据库
                self.db.add_follow_record(user_id, username)
                logger.info(f"成功关注用户: {username} ({user_id})")
                return True
            else:
                logger.error("无效的粉丝项格式")
                return False
                
        except Exception as e:
            logger.error(f"关注用户失败: {str(e)}")
            # 保存错误截图
            save_screenshot(self.driver, "error", level="ERROR")
            return False
            
    def unfollow_user(self, username, user_id):
        """
        取消关注用户
        
        参数:
            username: 用户名
            user_id: 用户ID
            
        返回:
            成功返回True，失败返回False
        """
        try:
            logger.info(f"准备取消关注用户: {username} ({user_id})")
            
            # 保存操作前的截图
            save_screenshot(self.driver, f"unfollow_{username}_before", level="NORMAL")
            
            # 查找已关注按钮
            followed_buttons = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), '已关注') or contains(text(), '互相关注')] | //div[contains(@class, 'followed')]")
            
            if not followed_buttons:
                logger.warning(f"未找到已关注按钮: {username}")
                save_screenshot(self.driver, f"unfollow_{username}_not_found", level="ERROR")
                return False
                
            # 点击已关注按钮
            followed_btn = followed_buttons[0]
            try:
                followed_btn.click()
                self.random_sleep(1, 2)
            except ElementClickInterceptedException:
                logger.warning(f"点击已关注按钮被拦截，尝试使用JavaScript点击: {username}")
                self.driver.execute_script("arguments[0].click();", followed_btn)
                self.random_sleep(1, 2)
            
            # 查找取消关注确认按钮
            confirm_buttons = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), '取消关注')] | //div[contains(text(), '取消关注')]")
            
            if not confirm_buttons:
                logger.warning(f"未找到取消关注确认按钮: {username}")
                save_screenshot(self.driver, f"unfollow_{username}_no_confirm", level="ERROR")
                return False
                
            # 点击确认按钮
            confirm_btn = confirm_buttons[0]
            try:
                confirm_btn.click()
                self.random_sleep(1, 2)
            except ElementClickInterceptedException:
                logger.warning(f"点击确认按钮被拦截，尝试使用JavaScript点击: {username}")
                self.driver.execute_script("arguments[0].click();", confirm_btn)
                self.random_sleep(1, 2)
            
            # 保存操作后的截图
            save_screenshot(self.driver, f"unfollow_{username}_after", level="NORMAL")
            
            # 更新数据库
            self.db.remove_follow_record(user_id)
            logger.info(f"成功取消关注用户: {username} ({user_id})")
            return True
            
        except Exception as e:
            logger.error(f"取消关注用户失败: {username} ({user_id}), 错误: {str(e)}")
            # 保存错误截图
            save_screenshot(self.driver, f"unfollow_{username}_error", level="ERROR")
            return False