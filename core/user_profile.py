"""
用户资料模块

该模块提供了访问和处理用户资料的功能。
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    ElementClickInterceptedException,
    NoSuchElementException
)
import re
import time
from .logger import logger, save_screenshot, save_html
from .selectors import USER_PROFILE, COMMON

class UserProfileManager:
    """用户资料管理类，负责访问和处理用户资料"""
    
    def __init__(self, browser_manager):
        """
        初始化用户资料管理器
        
        参数:
            browser_manager: 浏览器管理器对象
        """
        self.browser_manager = browser_manager
        self.driver = browser_manager.driver
        self.wait = browser_manager.wait
        self.random_sleep = browser_manager.random_sleep
        
    def visit_user_profile(self, username):
        """
        访问用户主页
        
        参数:
            username: 用户名或用户主页URL
            
        返回:
            成功返回True，失败抛出异常
        """
        try:
            # 构建用户主页URL
            if username.startswith("http"):
                # 如果是完整URL，直接使用
                url = username
            elif "/" in username:
                # 如果包含斜杠，可能是相对路径
                url = f"https://www.douyin.com{username if username.startswith('/') else '/' + username}"
            else:
                # 否则，假设是用户ID
                url = f"https://www.douyin.com/user/{username}"
                
            logger.info(f"访问用户主页: {url}")
            
            # 访问用户主页
            self.driver.get(url)
            
            # 等待页面加载
            self.random_sleep(5, 8)
            
            # 检查是否成功加载用户页面
            try:
                # 检查URL是否包含用户ID
                current_url = self.driver.current_url
                if username not in current_url:
                    logger.warning(f"当前URL不包含目标用户ID: {current_url}")
                
                # 检查页面标题
                title = self.driver.title
                logger.info(f"页面标题: {title}")
                
                # 检查是否有错误信息
                error_elements = self.driver.find_elements(By.XPATH, "//div[contains(text(), '错误') or contains(text(), '找不到') or contains(text(), '不存在')]")
                if error_elements:
                    for elem in error_elements:
                        logger.warning(f"页面可能包含错误信息: {elem.text}")
                        
                # 检查是否有用户信息元素
                user_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'author') or contains(@class, 'user')]")
                if not user_elements:
                    logger.warning("未找到用户信息元素")
                else:
                    logger.info(f"找到 {len(user_elements)} 个可能的用户信息元素")
                    
            except Exception as e:
                logger.warning(f"检查页面加载状态时出错: {str(e)}")
            
            # 保存页面截图
            save_screenshot(self.driver, "user_profile", level="NORMAL", user_id=username)
            save_html(self.driver, "user_profile", user_id=username)
                
            return True
        except Exception as e:
            logger.error(f"访问用户主页失败: {str(e)}")
            # 保存错误截图
            save_screenshot(self.driver, "error", level="ERROR")
            raise
            
    def click_fans_tab(self):
        """
        点击粉丝标签并获取粉丝数量
        
        返回:
            成功返回(True, fans_count)，失败抛出异常
        """
        try:
            # 保存点击前的URL和截图
            before_url = self.driver.current_url
            logger.info(f"点击粉丝标签前的URL: {before_url}")
            save_screenshot(self.driver, "before_click_fans", level="CRITICAL")
            save_html(self.driver, "before_click_fans")
            
            # 尝试查找新版粉丝按钮
            logger.info("尝试查找新版粉丝按钮...")
            
            try:
                # 使用精确的选择器查找新版粉丝按钮
                new_fans_selector = '//div[@data-e2e="user-info-fans"]'
                logger.info(f"尝试使用新版粉丝按钮选择器: {new_fans_selector}")
                
                fans_button = self.driver.find_element(By.XPATH, new_fans_selector)
                logger.info("找到新版粉丝按钮")
                
                # 获取粉丝数量
                try:
                    fans_count_element = fans_button.find_element(By.XPATH, './/div[contains(@class, "C1cxu0Vq")]')
                    fans_count_text = fans_count_element.text
                    fans_count = int(fans_count_text.replace('万', '0000').replace('亿', '00000000'))
                    logger.info(f"获取到粉丝数量: {fans_count}")
                except Exception as e:
                    logger.warning(f"获取粉丝数量失败: {str(e)}")
                    fans_count = 0
                
                # 记录元素信息
                element_text = fans_button.text
                element_class = fans_button.get_attribute("class")
                element_data_e2e = fans_button.get_attribute("data-e2e")
                logger.info(f"新版粉丝按钮信息: 文本='{element_text}', 类名='{element_class}', data-e2e='{element_data_e2e}'")
                
                # 滚动到元素位置
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fans_button)
                self.random_sleep(1, 2)
                
                # 使用JavaScript点击
                logger.info("使用JavaScript点击新版粉丝按钮")
                self.driver.execute_script("arguments[0].click();", fans_button)
                self.random_sleep(3, 5)
                
                # 保存点击后的截图
                save_screenshot(self.driver, "after_click_new_fans_button", level="CRITICAL")
                
                # 等待粉丝列表容器出现
                container_selectors = [
                    "//div[@data-e2e='user-fans-container']",
                    "//div[contains(@class, 'FjupSA6k')]"
                ]
                
                container_found = False
                max_retries = 3
                retry_count = 0
                
                while not container_found and retry_count < max_retries:
                    for selector in container_selectors:
                        try:
                            self.wait.until(
                                EC.presence_of_element_located((By.XPATH, selector))
                            )
                            logger.info(f"检测到粉丝列表容器: {selector}")
                            container_found = True
                            break
                        except:
                            continue
                    
                    if not container_found:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.warning(f"未检测到粉丝列表容器，第 {retry_count} 次重试...")
                            self.random_sleep(2, 3)
                            # 重新点击
                            self.driver.execute_script("arguments[0].click();", fans_button)
                            self.random_sleep(3, 5)
                
                if container_found:
                    logger.info("成功加载粉丝列表")
                    return True, fans_count
                else:
                    logger.error("无法加载粉丝列表")
                    raise Exception("无法加载粉丝列表")
                
            except NoSuchElementException:
                logger.warning("未找到新版粉丝按钮，尝试其他选择器")
                raise
            
        except Exception as e:
            logger.error(f"点击粉丝标签失败: {str(e)}")
            save_screenshot(self.driver, "error", level="ERROR")
            raise 