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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import re

class FollowListManager:
    """关注列表管理类，负责处理关注列表相关操作"""
    
    def __init__(self, browser_manager, db, config):
        """
        初始化关注列表管理器
        
        参数:
            browser_manager: 浏览器管理器对象
            db: 数据库对象
            config: 配置对象
        """
        self.browser_manager = browser_manager
        self.db = db
        self.config = config
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
                    
                    # 尝试查找用户名元素 - 使用更精确的选择器
                    username = "未知用户"
                    username_selectors = [
                        ".//span[contains(@class, 'arnSiSbK')]",
                        ".//a[contains(@class, 'uz1VJwFY')]//span//span[contains(@class, 'arnSiSbK')]",
                        ".//div[contains(@class, 'kUKK9Qal')]//a//span//span[contains(@class, 'arnSiSbK')]",
                        ".//span[contains(@class, 'name') or contains(@class, 'nickname')]", 
                        ".//div[contains(@class, 'name') or contains(@class, 'nickname')]",
                        ".//div[contains(@class, 'X8ljGzft')]//div[contains(@class, 'kUKK9Qal')]//a//span",
                        ".//a[contains(@href, '/user/')]//span"
                    ]
                    
                    for selector in username_selectors:
                        name_elements = parent_element.find_elements(By.XPATH, selector)
                        if name_elements:
                            text_content = name_elements[0].text.strip()
                            if text_content:
                                username = text_content
                                logger.info(f"通过选择器 {selector} 找到用户名: {username}")
                                break
                    
                    # 如果上述方法未能提取用户名，尝试使用JavaScript
                    if username == "未知用户":
                        try:
                            username = self.driver.execute_script("""
                                var element = arguments[0];
                                // 尝试查找arnSiSbK类的span元素
                                var nameElements = element.querySelectorAll('span.arnSiSbK');
                                if (nameElements.length > 0) {
                                    return nameElements[0].textContent.trim();
                                }
                                
                                // 尝试查找所有嵌套的span元素
                                var spans = element.querySelectorAll('span span span');
                                for (var i = 0; i < spans.length; i++) {
                                    var text = spans[i].textContent.trim();
                                    if (text && text.length > 0) {
                                        return text;
                                    }
                                }
                                
                                return "未知用户";
                            """, parent_element)
                            if username != "未知用户":
                                logger.info(f"通过JavaScript找到用户名: {username}")
                        except Exception as e:
                            logger.warning(f"使用JavaScript提取用户名失败: {str(e)}")
                        
                    # 尝试查找用户ID元素
                    id_elements = parent_element.find_elements(By.XPATH, 
                        ".//span[contains(@class, 'id') or contains(@class, 'unique')] | .//div[contains(@class, 'id') or contains(@class, 'unique')]")
                    
                    user_id = None
                    if id_elements:
                        user_id = id_elements[0].text
                        # 有时候用户ID会带有@前缀，需要去掉
                        if user_id and user_id.startswith('@'):
                            user_id = user_id[1:]
                    
                    # 如果没有找到用户ID，尝试从链接中提取
                    if not user_id:
                        link_elements = parent_element.find_elements(By.XPATH, ".//a[contains(@href, '/user/')]")
                        if link_elements:
                            href = link_elements[0].get_attribute('href')
                            if href and '/user/' in href:
                                user_id = href.split('/user/')[-1].split('?')[0]
                                logger.info(f"从链接中提取用户ID: {user_id}")
                    
                    # 如果仍然没有找到用户ID，使用时间戳作为临时ID
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
                    self.random_sleep(2, 3)  # 增加等待时间，等待弹窗出现
                    
                    # 检查是否出现弹窗
                    popup_found = self.check_and_handle_follow_popup()
                    if popup_found:
                        logger.info("检测到关注弹窗并已处理")
                    
                except ElementClickInterceptedException:
                    # 如果常规点击失败，尝试JavaScript点击
                    logger.info(f"常规点击失败，尝试JavaScript点击: {username}")
                    self.driver.execute_script("arguments[0].click();", follow_btn)
                    self.random_sleep(2, 3)  # 增加等待时间，等待弹窗出现
                    
                    # 检查是否出现弹窗
                    popup_found = self.check_and_handle_follow_popup()
                    if popup_found:
                        logger.info("检测到关注弹窗并已处理")
                        
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
            
    def check_and_handle_follow_popup(self):
        """
        检查并处理关注按钮点击后出现的弹窗
        
        返回:
            如果找到并处理了弹窗返回True，否则返回False
        """
        try:
            # 保存弹窗截图
            save_screenshot(self.driver, "follow_popup", level="NORMAL")
            
            # 检查弹窗是否存在 - 使用截图中的类名精确定位
            logger.info("检查关注弹窗是否存在...")
            popup_found = False
            popup_element = None
            
            # 根据截图中的类名定义更精确的选择器
            popup_selectors = [
                "//div[contains(@class, 'lg1KBICm k5PKYkwW GjZZha0A')]",  # 根据截图中的类名
                "//div[contains(@class, 'lg1KBICm')]",  # 备用选择器
                "//div[contains(@class, 'modal') or contains(@class, 'popup')]",  # 通用备用选择器
                "//div[.//span[contains(text(), '关注')] and .//span[contains(text(), '粉丝')]]",
                "//div[contains(., '关注') and contains(., '粉丝') and .//button[contains(@class, 'close')]]",
                "//div[.//div[contains(text(), '相互关注') or contains(text(), '互相关注') or contains(text(), '已关注')]]"
            ]
            
            for selector in popup_selectors:
                try:
                    popup_elements = self.driver.find_elements(By.XPATH, selector)
                    if popup_elements:
                        logger.info(f"通过元素选择器找到关注弹窗: {selector}")
                        popup_found = True
                        popup_element = popup_elements[0]
                        break
                    else:
                        logger.warning(f"未找到关注弹窗: {selector}")
                except Exception as e:
                    logger.warning(f"使用选择器 {selector} 查找关注弹窗失败: {str(e)}")
            
            if not popup_found:
                logger.info("未检测到关注弹窗")
                return False
            
            # 根据截图中的HTML结构定义更精确的用户项选择器
            user_item_selectors = [
                ".//div[contains(@class, 'MryVEcQw')]",  # 根据截图中的类名
                ".//div[contains(@class, 'uMlSMsI')]",   # 根据截图中的类名
                ".//div[contains(@class, 'i5YKH7Ag')]",  # 根据截图中的类名
                ".//div[contains(@class, '15U4dMnB')]",
                ".//div[contains(@class, 'ycRKGMm')]/..",
                ".//button[contains(@class, 'semi-button-secondary')]/..",
                ".//button[contains(@class, 'semi-button') and contains(@class, 'semi-button-secondary')]/..",
                ".//div[contains(@class, 'semi-button-content')]/../../..",
                ".//div[.//button[contains(@class, 'semi-button')]]",
                ".//div[.//span[contains(@class, 'semi-button-content')]]",
                ".//div[.//div[contains(text(), '已关注') or contains(text(), '相互关注')]]"
            ]
            
            # 尝试滚动弹窗以加载更多用户
            logger.info("尝试滚动弹窗以加载更多用户...")
            max_scroll_times = 5
            
            for i in range(max_scroll_times):
                # 使用JavaScript滚动弹窗
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", popup_element)
                logger.info(f"滚动弹窗 ({i+1}/{max_scroll_times})...")
                self.random_sleep(1, 2)
                
                # 保存滚动后的截图
                save_screenshot(self.driver, f"follow_popup_scroll_{i}", level="DEBUG")
            
            # 查找未互相关注的用户并关注
            user_items = []
            for selector in user_item_selectors:
                try:
                    items = popup_element.find_elements(By.XPATH, selector)
                    if items:
                        logger.info(f"在弹窗中找到 {len(items)} 个用户项: {selector}")
                        user_items = items
                        break
                    else:
                        logger.warning(f"未找到用户项: {selector}")
                except Exception as e:
                    logger.warning(f"使用选择器 {selector} 查找用户项失败: {str(e)}")
            
            if user_items:
                # 处理每个用户项
                for item in user_items:
                    try:
                        # 检查是否是互相关注
                        mutual_selectors = [
                            ".//button[contains(@class, 'semi-button-secondary')]//div[contains(text(), '相互关注')]",
                            ".//div[contains(@class, 'zPZJ3j40') and contains(text(), '相互关注')]",
                            ".//span[contains(@class, 'semi-button-content')]//div[contains(text(), '相互关注')]",
                            ".//button[contains(@class, 'xjIRvxqr')]//div[contains(text(), '相互关注')]"
                        ]
                        
                        is_mutual = False
                        for mutual_selector in mutual_selectors:
                            mutual_elems = item.find_elements(By.XPATH, mutual_selector)
                            if mutual_elems:
                                is_mutual = True
                                break
                        
                        # 如果不是互相关注，尝试关注
                        if not is_mutual:
                            # 提取用户名 - 使用截图中的类名精确匹配
                            username = ""
                            username_selectors = [
                                ".//div[contains(@class, 'QeORD5K8')]",  # 根据截图中的类名
                                ".//div[contains(@class, 'FjupSA6k')]",  # 根据截图中的类名
                                ".//span[contains(@class, 'arnSiSbK')]",
                                ".//a[contains(@class, 'uz1VJwFY')]//span//span[contains(@class, 'arnSiSbK')]",
                                ".//div[contains(@class, 'kUKK9Qal')]//a//span//span[contains(@class, 'arnSiSbK')]",
                                ".//div[contains(@class, 'X8ljGzft')]//div[contains(@class, 'kUKK9Qal')]//a//span",
                                ".//a[contains(@href, '/user/')]//span"
                            ]
                            
                            for username_selector in username_selectors:
                                try:
                                    username_elements = item.find_elements(By.XPATH, username_selector)
                                    if username_elements:
                                        text_content = username_elements[0].text.strip()
                                        if text_content:
                                            username = text_content
                                            logger.info(f"找到用户名: {username}")
                                            break
                                except Exception as e:
                                    logger.warning(f"使用选择器 {username_selector} 提取用户名失败: {str(e)}")
                            
                            # 如果仍然没有找到用户名，使用默认值
                            if not username:
                                username = "弹窗用户"
                            
                            # 查找关注按钮
                            follow_button_selectors = [
                                ".//button[contains(@class, 'semi-button-primary')]",
                                ".//button[contains(text(), '关注') and not(contains(text(), '已关注')) and not(contains(text(), '相互关注'))]",
                                ".//div[contains(text(), '关注') and not(contains(text(), '已关注')) and not(contains(text(), '相互关注'))]"
                            ]
                            
                            for button_selector in follow_button_selectors:
                                follow_buttons = item.find_elements(By.XPATH, button_selector)
                                if follow_buttons:
                                    # 点击关注按钮
                                    logger.info(f"在弹窗中点击关注用户: {username}")
                                    follow_buttons[0].click()
                                    self.random_sleep(1, 2)
                                    break
                    except Exception as e:
                        logger.warning(f"处理弹窗中的用户项失败: {str(e)}")
            else:
                logger.warning("未在弹窗中找到任何用户项")
            
            # 关闭弹窗
            try:
                # 尝试点击关闭按钮
                close_button_selectors = [
                    ".//button[contains(@class, 'close')]",
                    ".//div[contains(@class, 'close')]",
                    ".//span[contains(@class, 'close')]",
                    ".//i[contains(@class, 'close')]",
                    ".//button[contains(@aria-label, 'Close') or contains(@aria-label, '关闭')]"
                ]
                
                close_button_found = False
                for selector in close_button_selectors:
                    close_buttons = popup_element.find_elements(By.XPATH, selector)
                    if close_buttons:
                        close_buttons[0].click()
                        logger.info(f"通过元素选择器找到并点击了关闭按钮: {selector}")
                        close_button_found = True
                        self.random_sleep(1, 2)
                        break
                
                # 如果没有找到关闭按钮，尝试使用ESC键
                if not close_button_found:
                    logger.info("尝试使用ESC键关闭弹窗")
                    actions = ActionChains(self.driver)
                    actions.send_keys(Keys.ESCAPE).perform()
                    self.random_sleep(1, 2)
            except Exception as e:
                logger.warning(f"关闭弹窗失败: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"处理关注弹窗失败: {str(e)}")
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

    def handle_task_failure(self, error_message, error, screenshot_name=None):
        """
        处理任务失败
        """
        logger.error(f"{error_message}: {str(error)}")
        
        # 检查是否是会话失效错误
        if "invalid session id" in str(error):
            logger.error("检测到会话失效错误，尝试重启浏览器")
            self.browser_manager.restart_browser()
        
        # 保存截图和HTML
        if screenshot_name:
            try:
                save_screenshot(self.driver, screenshot_name)
                save_html(self.driver, screenshot_name)
            except:
                logger.error("保存截图和HTML失败")
    
    def run_check_follows_task(self):
        """
        执行检查关注列表任务
        
        该任务会检查当前账号的关注列表，找出未回关的用户，并标记为待取关
        """
        try:
            logger.info("开始执行检查关注列表任务...")
            
            # 打开关注列表
            try:
                # 打开用户主页 - 使用/user/self而不是/user
                self.driver.get("https://www.douyin.com/user/self")
                time.sleep(3)
                
                # 点击关注按钮打开关注列表
                logger.info("点击关注按钮打开关注列表...")
                follow_button = None
                try:
                    # 直接使用data-e2e属性查找关注按钮
                    follow_button = self.driver.find_element(By.XPATH, "//div[@data-e2e='user-info-follow']")
                    follow_button.click()
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"直接查找关注按钮失败: {str(e)}")
                    # 尝试备用选择器
                    follow_button_selectors = [
                        "//div[contains(@class, 'count-item') and contains(., '关注')]",
                        "//div[contains(@class, 'tab-item') and contains(., '关注')]",
                        "//span[contains(text(), '关注')]/parent::div",
                        "//div[contains(@class, 'author-info-follow')]//span[contains(text(), '关注')]",
                        "//div[contains(@class, 'author-info-follow')]",
                        "//div[contains(@class, 'count-item')]//span[contains(text(), '关注')]",
                        "//div[contains(@class, 'count-item')]//span[contains(text(), '关注')]/parent::div"
                    ]
                    
                    button_clicked = False
                    for selector in follow_button_selectors:
                        try:
                            logger.info(f"尝试使用备用选择器: {selector}")
                            buttons = self.driver.find_elements(By.XPATH, selector)
                            if buttons:
                                logger.info(f"找到 {len(buttons)} 个可能的关注按钮")
                                for i, button in enumerate(buttons):
                                    try:
                                        if button.is_displayed():
                                            button_text = button.text.strip()
                                            logger.info(f"按钮 {i+1} 文本: '{button_text}'")
                                            if "关注" in button_text:
                                                logger.info(f"尝试点击按钮 {i+1}")
                                                button.click()
                                                time.sleep(2)
                                                logger.info(f"成功点击关注按钮: {selector}")
                                                button_clicked = True
                                                break
                                    except Exception as e:
                                        logger.warning(f"尝试点击按钮 {i+1} 失败: {str(e)}")
                                        continue
                            
                            if button_clicked:
                                break
                        except Exception as e:
                            logger.warning(f"使用选择器 {selector} 查找关注按钮失败: {str(e)}")
                            continue
                    
                    # 如果所有选择器都失败，尝试使用JavaScript点击
                    if not button_clicked:
                        logger.info("所有选择器都失败，尝试使用JavaScript点击关注按钮")
                        try:
                            self.driver.execute_script("""
                                // 尝试查找关注按钮
                                var followButtons = document.querySelectorAll('div[class*="count-item"]');
                                for (var i = 0; i < followButtons.length; i++) {
                                    if (followButtons[i].textContent.includes('关注')) {
                                        followButtons[i].click();
                                        return true;
                                    }
                                }
                                return false;
                            """)
                            logger.info("通过JavaScript点击关注按钮")
                            time.sleep(2)
                        except Exception as e:
                            logger.warning(f"通过JavaScript点击关注按钮失败: {str(e)}")
                            self.handle_task_failure("点击关注按钮失败", e, "check_follows_button_error")
                            return False
                
                # 检查弹窗是否存在 - 使用截图中的类名精确定位
                logger.info("检查关注列表弹窗是否存在...")
                popup_found = False
                popup_element = None
                
                # 根据截图中的类名定义更精确的选择器
                popup_selectors = [
                    "//div[contains(@class, 'i5YKH7Ag')]",  # 根据截图中的类名
                    "//div[contains(@class, 'lg1KBICm k5PKYkwW GjZZha0A')]",  # 备用类名
                    "//div[contains(@class, 'Qe0RD5K8')]",  # 备用类名
                    "//div[contains(@class, 'FjupSA6k')]",  # 备用类名
                    "//div[@data-e2e='user-fans-container']",  # 使用data-e2e属性
                    "//div[contains(@class, 'semi-tabs-content')]",  # 备用选择器
                    "//div[contains(@class, 'semi-tabs-pane-active')]",  # 备用选择器
                    "//div[contains(@class, 'semi-modal-content')]",
                    "//div[contains(@class, 'semi-modal-wrapper')]",
                    "//div[contains(@class, 'semi-modal')]"
                ]
                
                for popup_selector in popup_selectors:
                    try:
                        popup_elements = self.driver.find_elements(By.XPATH, popup_selector)
                        if popup_elements:
                            logger.info(f"通过元素选择器找到关注列表弹窗: {popup_selector}")
                            popup_found = True
                            popup_element = popup_elements[0]
                            break
                        else:
                            logger.warning(f"未找到关注列表弹窗: {popup_selector}")
                    except Exception as e:
                        logger.warning(f"使用选择器 {popup_selector} 查找关注列表弹窗失败: {str(e)}")
                
                if not popup_found:
                    logger.warning("未能找到关注列表弹窗")
                    self.handle_task_failure("未找到关注列表弹窗", Exception("未找到关注列表弹窗"), "check_follows_no_popup")
                    return False
                
                # 获取关注总数
                total_follows_count = 0
                try:
                    # 尝试从标签页标题获取关注总数
                    title_selectors = [
                        "//div[contains(@class, 'semi-tabs-tab-active')]",  # 活动标签
                        "//div[@role='tab' and @aria-selected='true']",  # 活动标签备用
                        "//div[contains(@class, 'semi-tabs-tab') and contains(text(), '关注')]",  # 关注标签
                        "//div[contains(@class, 'title') and contains(text(), '关注')]",
                        "//div[contains(text(), '关注 (')]"
                    ]
                    
                    for selector in title_selectors:
                        try:
                            tab_elements = self.driver.find_elements(By.XPATH, selector)
                            if tab_elements:
                                tab_text = tab_elements[0].text.strip()
                                # 提取括号中的数字
                                match = re.search(r'关注\s*\(?(\d+)\)?', tab_text)
                                if match:
                                    total_follows_count = int(match.group(1))
                                    logger.info(f"从标签页获取到关注总数: {total_follows_count}")
                                    break
                        except Exception as e:
                            logger.warning(f"从标签页获取关注总数失败: {str(e)}")
                    
                    if total_follows_count == 0:
                        logger.warning("未能从标签页获取关注总数，将尝试从其他元素获取")
                except Exception as e:
                    logger.warning(f"获取关注总数失败: {str(e)}")
                
                # 获取关注列表
                logger.info("获取关注列表...")
                
                # 根据截图中的HTML结构定义更精确的用户项选择器
                user_item_selectors = [
                    ".//div[@data-e2e='user-fans-container']//div[contains(@class, 'i5U4dMnB')]",  # 主要选择器
                    ".//div[contains(@class, 'FjupSA6k')]//div[contains(@class, 'i5U4dMnB')]",  # 备用选择器
                    ".//div[contains(@class, 'i5U4dMnB')]",  # 备用选择器
                    ".//div[contains(@class, 'PETaiSYi')]",  # 备用选择器
                    ".//div[contains(@class, 'X8ljGzft')]"  # 备用选择器
                ]
                
                # 选择最佳的用户项选择器
                best_selector = None
                max_items = 0
                
                for user_selector in user_item_selectors:
                    try:
                        items = popup_element.find_elements(By.XPATH, user_selector)
                        if items and len(items) > max_items:
                            max_items = len(items)
                            best_selector = user_selector
                            logger.info(f"通过元素选择器找到 {len(items)} 个关注用户项: {user_selector}")
                    except Exception as e:
                        logger.warning(f"使用选择器 {user_selector} 查找关注用户项失败: {str(e)}")
                
                if not best_selector:
                    self.handle_task_failure("未找到关注用户列表项", Exception("未找到关注用户列表项"), "check_follows_no_users")
                    return False
                
                # 处理找到的用户项
                logger.info(f"使用选择器 {best_selector} 开始获取关注用户")
                
                # 用户名选择器
                username_selectors = [
                    ".//div[contains(@class, 'kUKK9Qal')]//span",  # 主要选择器
                    ".//div[contains(@class, 'arnSiSbK')]",  # 备用选择器
                    ".//a[contains(@class, 'uz1VJwFY')]//span",  # 备用选择器
                    ".//p[contains(@class, 'kUKK9Qal')]",
                    ".//p[contains(@class, 'arnSiSbK')]",
                    ".//span[contains(@class, 'uz1VJwFY')]",
                    ".//span[contains(@class, 'nickname')]",
                    ".//span[contains(@class, 'title')]"
                ]
                
                # 关注状态选择器
                follow_status_selectors = [
                    ".//div[contains(@class, 'zPZJ3j40')]",  # 主要选择器
                    ".//button[contains(@class, 'xjIRvxqr')]//div",  # 备用选择器
                    ".//button[contains(@class, 'xjIRvxqr')]",  # 按钮本身
                    ".//div[contains(@class, 'semi-button-content')]",  # 按钮内容
                    ".//div[contains(@class, 'semi-button')]",  # 通用按钮类
                    ".//div[contains(@class, 'follow-button')]",  # 关注按钮
                    ".//div[contains(@class, 'follow-state')]",  # 关注状态
                    ".//button[contains(@class, 'zPZJ3j40')]",
                    ".//button[contains(@class, 'xjIRvxqr')]",
                    ".//button[contains(@class, 'follow-button')]",
                    ".//div[contains(@class, 'follow-status')]"
                ]
                
                # 用户ID选择器
                user_id_selectors = [
                    ".//a[contains(@href, '/user/')]",  # 用户链接
                ]
                
                # 存储关注用户信息
                follow_items = []
                processed_usernames = set()  # 用于跟踪已处理的用户名，避免重复
                
                # 滚动加载所有用户
                last_user_count = 0
                no_new_users_count = 0
                max_scroll_attempts = 20  # 最大滚动尝试次数
                
                for scroll_attempt in range(max_scroll_attempts):
                    # 获取当前加载的用户项
                    user_items = self.driver.find_elements(By.XPATH, best_selector)
                    current_user_count = len(user_items)
                    
                    logger.info(f"当前已加载 {current_user_count} 个关注用户项")
                    
                    # 处理新加载的用户
                    for i in range(last_user_count, current_user_count):
                        if i >= len(user_items):
                            break
                            
                        user_item = user_items[i]
                        
                        # 提取用户名
                        username = ""
                        for selector in username_selectors:
                            try:
                                username_elements = user_item.find_elements(By.XPATH, selector)
                                if username_elements:
                                    username = username_elements[0].text.strip()
                                    if username:
                                        break
                            except Exception as e:
                                logger.debug(f"使用选择器 {selector} 获取用户名失败: {str(e)}")
                        
                        if not username:
                            logger.warning(f"无法获取第 {i+1} 个用户的用户名")
                            continue
                            
                        # 检查是否已处理过该用户
                        if username in processed_usernames:
                            continue
                            
                        processed_usernames.add(username)
                        
                        # 提取关注状态
                        follow_status = ""
                        for selector in follow_status_selectors:
                            try:
                                follow_buttons = user_item.find_elements(By.XPATH, selector)
                                if follow_buttons:
                                    for btn_index in range(len(follow_buttons)):
                                        try:
                                            button = follow_buttons[btn_index]
                                            button_class = button.get_attribute("class")
                                            button_text = button.text.strip()
                                            
                                            # 根据按钮类名或文本判断关注状态
                                            if "相互关注" in button_text:
                                                follow_status = "相互关注"
                                                break
                                            elif "following" in button_class.lower() or "已关注" in button_text:
                                                follow_status = "已关注"
                                                break
                                        except Exception as e:
                                            logger.debug(f"检查按钮 {btn_index} 失败: {str(e)}")
                                            continue
                            except Exception as e:
                                logger.debug(f"获取按钮列表失败: {str(e)}")
                        
                        # 简化后续检查，直接默认为已关注
                        if not follow_status:
                            # 在关注列表中的用户默认为已关注状态
                            follow_status = "已关注"
                            logger.info(f"用户 {username} 的关注状态无法确定，默认为'已关注'")
                        
                        # 提取用户ID - 限制尝试次数
                        user_id = ""
                        max_id_attempts = 2
                        id_attempts = 0
                        
                        for selector in user_id_selectors:
                            if id_attempts >= max_id_attempts:
                                break
                                
                            try:
                                link_elements = user_item.find_elements(By.XPATH, selector)
                                if link_elements:
                                    href = link_elements[0].get_attribute('href')
                                    if href and '/user/' in href:
                                        user_id = href.split('/user/')[-1].split('?')[0]
                                        break
                            except Exception as e:
                                logger.debug(f"使用选择器 {selector} 获取用户ID失败: {str(e)}")
                            
                            id_attempts += 1
                        
                        logger.info(f"用户 {username} 的关注状态: {follow_status}")
                        
                        # 添加到关注列表
                        follow_items.append({
                            "username": username,
                            "status": follow_status,
                            "user_id": user_id
                        })
                    
                    # 检查是否需要继续滚动
                    if current_user_count == last_user_count:
                        no_new_users_count += 1
                        if no_new_users_count >= 3:  # 连续3次没有新用户，停止滚动
                            logger.info(f"连续 {no_new_users_count} 次没有发现新用户，停止滚动")
                            break
                    else:
                        no_new_users_count = 0
                    
                    # 如果已经加载了所有用户，停止滚动
                    if total_follows_count > 0 and current_user_count >= total_follows_count:
                        logger.info(f"已加载所有 {total_follows_count} 个关注用户，停止滚动")
                        break
                    
                    # 滚动到最后一个用户项
                    if current_user_count > 0:
                        try:
                            last_user = user_items[current_user_count - 1]
                            self.driver.execute_script("arguments[0].scrollIntoView();", last_user)
                            time.sleep(1)  # 等待加载
                        except Exception as e:
                            logger.warning(f"滚动加载更多用户失败: {str(e)}")
                    
                    last_user_count = current_user_count
                
                logger.info("滚动加载完成，开始处理获取到的用户信息")
                
                # 检查是否获取到关注用户信息
                if follow_items:
                    # 统计有效处理的用户数
                    valid_users = len(follow_items)
                    total_loaded = len(processed_usernames)
                    
                    logger.info(f"成功获取 {valid_users} 个关注用户信息 (总加载用户数: {total_loaded}, 有效处理用户数: {valid_users})")
                    
                    if total_loaded > valid_users:
                        logger.warning(f"注意: 加载了 {total_loaded} 个用户项，但只成功处理了 {valid_users} 个用户信息")
                        logger.warning(f"可能原因: 1.有用户名为空 2.有重复用户 3.处理过程中出错")
                        
                        # 统计未处理的用户原因
                        try:
                            empty_username_count = 0
                            duplicate_username_count = 0
                            error_count = 0
                            
                            # 重新获取所有用户项
                            all_user_items = self.driver.find_elements(By.XPATH, best_selector)
                            
                            for user_item in all_user_items:
                                try:
                                    # 检查用户名
                                    item_username = ""
                                    for selector in username_selectors:
                                        try:
                                            username_elements = user_item.find_elements(By.XPATH, selector)
                                            if username_elements:
                                                item_username = username_elements[0].text.strip()
                                                if item_username:
                                                    break
                                        except:
                                            continue
                                    
                                    if not item_username:
                                        empty_username_count += 1
                                    elif list(processed_usernames).count(item_username) > 1:
                                        duplicate_username_count += 1
                                except:
                                    error_count += 1
                            
                            logger.warning(f"统计结果: 空用户名: {empty_username_count}, 重复用户: {duplicate_username_count}, 处理错误: {error_count}")
                            
                            # 尝试修复未处理的用户
                            logger.info("尝试修复未处理的用户...")
                            
                            for i, user_item in enumerate(all_user_items):
                                try:
                                    # 检查是否已经处理过
                                    fix_username = ""
                                    for selector in username_selectors:
                                        try:
                                            username_elements = user_item.find_elements(By.XPATH, selector)
                                            if username_elements:
                                                fix_username = username_elements[0].text.strip()
                                                if fix_username:
                                                    break
                                        except:
                                            continue
                                    
                                    if not fix_username or fix_username in processed_usernames:
                                        continue
                                    
                                    # 提取关注状态
                                    fix_follow_status = ""
                                    for selector in follow_status_selectors:
                                        try:
                                            follow_buttons = user_item.find_elements(By.XPATH, selector)
                                            if follow_buttons:
                                                for btn in follow_buttons:
                                                    try:
                                                        button_text = btn.text.strip()
                                                        button_class = btn.get_attribute("class")
                                                        
                                                        if "相互关注" in button_text:
                                                            fix_follow_status = "相互关注"
                                                            break
                                                        elif "following" in button_class.lower() or "已关注" in button_text:
                                                            fix_follow_status = "已关注"
                                                            break
                                                    except:
                                                        continue
                                        except:
                                            continue
                                    
                                    if not fix_follow_status:
                                        fix_follow_status = "已关注"
                                    
                                    # 提取用户ID
                                    fix_user_id = ""
                                    for selector in user_id_selectors:
                                        try:
                                            link_elements = user_item.find_elements(By.XPATH, selector)
                                            if link_elements:
                                                href = link_elements[0].get_attribute('href')
                                                if href and '/user/' in href:
                                                    fix_user_id = href.split('/user/')[-1].split('?')[0]
                                                    break
                                        except:
                                            continue
                                    
                                    # 添加到关注列表
                                    follow_items.append({
                                        "username": fix_username,
                                        "status": fix_follow_status,
                                        "user_id": fix_user_id
                                    })
                                    
                                    logger.info(f"修复并添加用户: {fix_username}")
                                except Exception as e:
                                    logger.warning(f"修复第 {i+1} 个用户时出错: {str(e)}")
                            
                            logger.info(f"修复后: 成功获取 {len(follow_items)} 个关注用户信息")
                        except Exception as e:
                            logger.warning(f"统计未处理用户时出错: {str(e)}")
                    
                    try:
                        # 统计关注情况
                        total_follows = len(follow_items)
                        mutual_follows = sum(1 for item in follow_items if "相互关注" in item['status'])
                        # 修改判断逻辑，只有明确标记为"已关注"的才算作未回关，排除状态无法确定的用户
                        non_mutual_follows = sum(1 for item in follow_items if "相互关注" not in item['status'] and "已关注" in item['status'])
                        
                        logger.info(f"关注列表统计: 总关注 {total_follows}, 互相关注 {mutual_follows}, 未回关 {non_mutual_follows}")
                        
                        # 找出未回关的用户 - 修改判断逻辑，只有明确标记为"已关注"的才算未回关，排除状态无法确定的用户
                        non_mutual_users = [item for item in follow_items if "相互关注" not in item['status'] and "已关注" in item['status']]
                        
                        if non_mutual_users:
                            logger.info(f"找到 {len(non_mutual_users)} 个未回关用户")
                            
                            # 将未回关用户信息保存到数据库，标记为待取关
                            marked_count = 0
                            
                            # 批量处理未回关用户，每批次处理一部分
                            batch_size = 10
                            for i in range(0, len(non_mutual_users), batch_size):
                                batch = non_mutual_users[i:i+batch_size]
                                
                                for user in batch:
                                    try:
                                        if user['user_id']:  # 确保有用户ID
                                            unfollow_days = self.config.get('operation', {}).get('unfollow_days', 3)
                                            if self.db.mark_user_for_unfollow(user['user_id'], user['username'], unfollow_days):
                                                marked_count += 1
                                    except Exception as e:
                                        logger.error(f"标记用户为待取关失败: {user['username']}, 错误: {str(e)}")
                                
                                # 每批次处理后休息一下
                                if i + batch_size < len(non_mutual_users):
                                    time.sleep(0.5)
                            
                            logger.info(f"已标记 {marked_count} 个用户为待取关")
                        else:
                            logger.info("没有找到未回关用户")
                    except Exception as e:
                        logger.error(f"处理关注用户数据时出错: {str(e)}")
                    
                    # 关闭弹窗
                    try:
                        logger.info("尝试关闭关注列表弹窗...")
                        
                        # 直接使用JavaScript精确定位并点击关闭按钮，这是最有效的方法
                        self.driver.execute_script("""
                            // 通过类名精确定位关闭按钮
                            var closeButtons = document.getElementsByClassName('KArYflhI');
                            if (closeButtons && closeButtons.length > 0) {
                                closeButtons[0].click();
                                return true;
                            }
                            
                            // 通过SVG类名定位
                            var svgButtons = document.getElementsByClassName('xlWtWI6P');
                            if (svgButtons && svgButtons.length > 0) {
                                svgButtons[0].parentNode.click();
                                return true;
                            }
                            
                            return false;
                        """)
                        
                        time.sleep(1)  # 等待关闭动画
                        logger.info("通过JavaScript精确定位并点击关闭按钮")
                        
                        # 验证弹窗是否已关闭
                        popup_still_exists = False
                        try:
                            # 检查弹窗是否仍然存在
                            for popup_selector in popup_selectors:
                                try:
                                    popup_elements = self.driver.find_elements(By.XPATH, popup_selector)
                                    if popup_elements and popup_elements[0].is_displayed():
                                        popup_still_exists = True
                                        break
                                except:
                                    continue
                            
                            if popup_still_exists:
                                # 如果弹窗仍然存在，尝试按ESC键关闭
                                logger.warning("JavaScript点击后弹窗仍然存在，尝试按ESC键关闭")
                                actions = ActionChains(self.driver)
                                actions.send_keys(Keys.ESCAPE).perform()
                                time.sleep(1)
                                
                                # 再次检查弹窗是否仍然存在
                                popup_still_exists = False
                                for popup_selector in popup_selectors:
                                    try:
                                        popup_elements = self.driver.find_elements(By.XPATH, popup_selector)
                                        if popup_elements and popup_elements[0].is_displayed():
                                            popup_still_exists = True
                                            break
                                    except:
                                        continue
                                
                                # 最后尝试刷新页面
                                if popup_still_exists:
                                    logger.warning("所有方法都无法关闭弹窗，尝试刷新页面")
                                    self.driver.refresh()
                                    time.sleep(2)
                            else:
                                logger.info("已关闭关注列表弹窗")
                        except Exception as e:
                            logger.warning(f"验证弹窗关闭状态时出错: {str(e)}")
                    except Exception as e:
                        logger.warning(f"关闭关注列表弹窗失败: {str(e)}")
                        # 最后尝试刷新页面
                        try:
                            self.driver.refresh()
                            time.sleep(2)
                            logger.info("通过刷新页面关闭弹窗")
                        except:
                            logger.warning("刷新页面失败")
                    
                    # 任务完成后休息一段时间，避免频繁执行
                    task_interval = self.config.get('task', {}).get('check_follows_interval', 3600)  # 默认1小时
                    logger.info(f"检查关注列表任务完成，将在 {task_interval} 秒后再次执行")
                    
                    return True
                else:
                    logger.warning("未获取到任何关注用户信息")
                    return False
                    
            except Exception as e:
                logger.error(f"打开关注列表失败: {str(e)}")
                self.handle_task_failure("打开关注列表失败", e, "open_follows_error")
                return False
                
        except Exception as e:
            logger.error(f"检查关注列表任务失败: {str(e)}")
            self.handle_task_failure("检查关注列表任务失败", e, "check_follows_error")
            return False