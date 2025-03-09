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
        点击粉丝标签
        
        返回:
            成功返回True，失败抛出异常
        """
        try:
            # 保存点击前的URL
            before_url = self.driver.current_url
            logger.info(f"点击粉丝标签前的URL: {before_url}")
            
            # 保存点击前的截图和HTML源码
            save_screenshot(self.driver, "before_click_fans", level="CRITICAL")
            save_html(self.driver, "before_click_fans")
            
            # 首先尝试通过URL参数切换到粉丝标签
            current_url = self.driver.current_url
            if "tab=fans_tab" not in current_url and "follower" not in current_url:
                # 构建粉丝标签URL
                if "?" in current_url:
                    fans_url = current_url.split("?")[0] + "?tab=fans_tab"
                else:
                    fans_url = current_url + "?tab=fans_tab"
                
                logger.info(f"通过URL参数切换到粉丝标签: {fans_url}")
                self.driver.get(fans_url)
                self.random_sleep(3, 5)
                
                # 保存URL切换后的截图
                save_screenshot(self.driver, "after_url_fans", level="CRITICAL")
                
                # 检查URL是否包含粉丝标签参数
                if "tab=fans_tab" in self.driver.current_url or "follower" in self.driver.current_url:
                    logger.info("成功通过URL切换到粉丝标签")
                    return True
            
            # 如果URL切换失败，尝试点击粉丝标签
            logger.info("URL切换失败或不适用，尝试点击粉丝标签...")
            
            # 尝试所有可能的粉丝标签选择器
            for selector in USER_PROFILE['FANS_TAB']:
                try:
                    logger.info(f"尝试使用选择器: {selector}")
                    fans_tab = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    # 记录元素信息
                    element_text = fans_tab.text
                    element_class = fans_tab.get_attribute("class")
                    logger.info(f"找到粉丝标签元素: 文本='{element_text}', 类名='{element_class}'")
                    
                    # 滚动到元素位置
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fans_tab)
                    self.random_sleep(2, 3)
                    
                    # 尝试点击
                    try:
                        fans_tab.click()
                        logger.info(f"成功点击粉丝标签: {element_text}")
                        self.random_sleep(3, 5)
                    except ElementClickInterceptedException:
                        # 如果常规点击失败，尝试JavaScript点击
                        self.driver.execute_script("arguments[0].click();", fans_tab)
                        logger.info(f"使用JavaScript点击粉丝标签: {element_text}")
                        self.random_sleep(3, 5)
                    
                    # 保存点击后的截图
                    save_screenshot(self.driver, "after_click_fans", level="CRITICAL")
                    
                    # 验证点击是否成功 - 检查URL或页面内容变化
                    after_url = self.driver.current_url
                    if after_url != before_url or "tab=fans_tab" in after_url or "follower" in after_url:
                        logger.info(f"URL已变化，点击成功: {after_url}")
                        return True
                    
                    # 检查页面内容是否包含粉丝列表
                    try:
                        # 等待粉丝列表出现
                        self.wait.until(
                            lambda driver: len(driver.find_elements(By.XPATH, '//div[contains(@class, "user-item")]')) > 0 or
                                         len(driver.find_elements(By.XPATH, '//div[contains(@class, "user-card")]')) > 0
                        )
                        logger.info("检测到粉丝列表元素，点击成功")
                        return True
                    except TimeoutException:
                        logger.warning("未检测到粉丝列表元素，点击可能失败")
                        # 继续尝试其他选择器
                        
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
                    continue
            
            # 如果所有选择器都失败，尝试特定的选择器
            logger.info("常规选择器失败，尝试特定选择器...")
            specific_selectors = [
                '//div[contains(@class, "tab-container")]//div[contains(text(), "粉丝")]',
                '//div[contains(@class, "count-item") and contains(., "粉丝")]',
                '//div[contains(@class, "author-card")]//div[contains(text(), "粉丝")]',
                '//div[contains(@class, "count-item") and .//span[contains(text(), "粉丝")]]',
                '//div[contains(@class, "tab-item") and .//span[contains(text(), "粉丝")]]',
                '//div[contains(@class, "tab-item") and contains(., "粉丝")]',
                '//div[contains(@class, "author-info-count")]//div[contains(text(), "粉丝") and contains(text(), "万")]',
                '//div[contains(@class, "author-info-count")]//span[contains(text(), "粉丝") and contains(text(), "万")]',
                '//div[contains(@class, "author-info-count")]//div[contains(text(), "粉丝") and contains(text(), "亿")]',
                '//div[contains(@class, "author-info-count")]//span[contains(text(), "粉丝") and contains(text(), "亿")]',
                '//div[contains(@class, "author-info-count")]//div[contains(text(), "粉丝") and contains(text(), "0") or contains(text(), "1") or contains(text(), "2") or contains(text(), "3") or contains(text(), "4") or contains(text(), "5") or contains(text(), "6") or contains(text(), "7") or contains(text(), "8") or contains(text(), "9")]',
                '//div[contains(@class, "author-info-count")]//span[contains(text(), "粉丝") and contains(text(), "0") or contains(text(), "1") or contains(text(), "2") or contains(text(), "3") or contains(text(), "4") or contains(text(), "5") or contains(text(), "6") or contains(text(), "7") or contains(text(), "8") or contains(text(), "9")]'
            ]
            
            # 尝试所有特定选择器
            for selector in specific_selectors:
                try:
                    logger.info(f"尝试使用特定选择器: {selector}")
                    element = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    # 记录元素信息
                    element_text = element.text
                    element_class = element.get_attribute("class")
                    logger.info(f"找到粉丝标签元素: 文本='{element_text}', 类名='{element_class}'")
                    
                    # 滚动到元素位置
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    self.random_sleep(2, 3)
                    
                    # 尝试点击
                    try:
                        element.click()
                        logger.info(f"成功点击粉丝标签: {element_text}")
                        self.random_sleep(3, 5)
                    except ElementClickInterceptedException:
                        # 如果常规点击失败，尝试JavaScript点击
                        self.driver.execute_script("arguments[0].click();", element)
                        logger.info(f"使用JavaScript点击粉丝标签: {element_text}")
                        self.random_sleep(3, 5)
                    
                    # 保存点击后的截图
                    save_screenshot(self.driver, "after_click_fans", level="CRITICAL")
                    
                    # 验证点击是否成功 - 检查URL或页面内容变化
                    after_url = self.driver.current_url
                    if after_url != before_url or "tab=fans_tab" in after_url or "follower" in after_url:
                        logger.info(f"URL已变化，点击成功: {after_url}")
                        return True
                    
                    # 检查页面内容是否包含粉丝列表
                    try:
                        # 等待粉丝列表出现
                        self.wait.until(
                            lambda driver: len(driver.find_elements(By.XPATH, '//div[contains(@class, "user-item")]')) > 0 or
                                         len(driver.find_elements(By.XPATH, '//div[contains(@class, "user-card")]')) > 0
                        )
                        logger.info("检测到粉丝列表元素，点击成功")
                        return True
                    except TimeoutException:
                        logger.warning("未检测到粉丝列表元素，点击可能失败")
                        # 继续尝试其他选择器
                        
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
                    continue
            
            # 如果所有方法都失败，尝试最后的方法：直接修改URL
            logger.info("所有点击方法失败，尝试直接修改URL...")
            
            # 提取用户ID
            current_url = self.driver.current_url
            user_id_match = re.search(r'/user/([^/?]+)', current_url)
            
            if user_id_match:
                user_id = user_id_match.group(1)
                fans_url = f"https://www.douyin.com/user/{user_id}?tab=fans_tab"
                logger.info(f"通过URL参数切换到粉丝标签: {fans_url}")
                self.driver.get(fans_url)
                self.random_sleep(3, 5)
                
                # 保存URL切换后的截图
                save_screenshot(self.driver, "after_url_fans", level="CRITICAL")
                
                # 检查URL是否包含粉丝标签参数
                if "tab=fans_tab" in self.driver.current_url:
                    logger.info("成功通过URL切换到粉丝标签")
                    return True
            
            # 如果所有方法都失败，抛出异常
            save_screenshot(self.driver, "error", level="ERROR")
            raise Exception("无法点击粉丝标签")
            
        except Exception as e:
            logger.error(f"点击粉丝标签失败: {str(e)}")
            save_screenshot(self.driver, "error", level="ERROR")
            raise 