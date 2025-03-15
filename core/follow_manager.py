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
        
    def check_and_handle_follow_popup(self):
        """
        检查并处理关注按钮点击后出现的弹窗
        
        返回:
            如果找到并处理了弹窗返回True，否则返回False
        """
        try:
            # 检查弹窗是否存在 - 使用data-e2e属性和DOM结构
            logger.info("检查关注弹窗是否存在...")
            popup_found = False
            popup_element = None
            
            # 使用data-e2e属性和DOM结构定位弹窗
            popup_selectors = [
                "//div[@data-e2e='user-fans-container']",  # 主要选择器,使用data-e2e属性
                "//div[.//button[@data-e2e='user-info-follow-btn']]/..",  # 基于关注按钮的父容器
                "//div[.//div[contains(@class, 'semi-modal-content')]]",  # 基于semi-modal结构
                "//div[.//div[contains(@class, 'semi-tabs-content')]]"  # 基于tabs结构
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
            
            # 基于DOM层级结构定位用户项
            user_items = []
            try:
                # 使用container的直接子元素层级结构查找用户项
                items = popup_element.find_elements(By.XPATH, "./div/div[.//a[contains(@href, '/user/')]]")
                if items:
                    logger.info(f"在弹窗中找到 {len(items)} 个用户项")
                    user_items = items
                else:
                    logger.warning("未找到用户项")
            except Exception as e:
                logger.warning(f"查找用户项失败: {str(e)}")

            if user_items:
                # 处理每个用户项
                for item in user_items:
                    try:
                        # 检查关注状态 - 使用按钮层级结构
                        follow_status = None
                        follow_button = None
                        
                        # 查找关注按钮 - 使用层级结构
                        buttons = item.find_elements(By.XPATH, ".//button[.//div[string-length(text()) > 0]]")
                        
                        for btn in buttons:
                            try:
                                # 获取按钮文本 - 使用层级结构
                                button_text = btn.find_element(By.XPATH, ".//div[string-length(text()) > 0]").text.strip()
                                
                                if "相互关注" in button_text:
                                    follow_status = "mutual"
                                    logger.info(f"检测到相互关注状态: {button_text}")
                                    break
                                elif "已关注" in button_text:
                                    follow_status = "following"
                                    logger.info(f"检测到已关注状态: {button_text}")
                                    break
                                elif "关注" in button_text:
                                    follow_button = btn
                                    follow_status = "not_following"
                                    logger.info(f"检测到未关注状态: {button_text}")
                                    break
                            except Exception as e:
                                logger.debug(f"获取按钮文本失败: {str(e)}")
                                continue
                        
                        # 如果不是互相关注,尝试关注
                        if follow_status == "not_following" and follow_button:
                            # 提取用户名 - 使用层级结构
                            username = ""
                            try:
                                # 使用链接内的span层级获取用户名
                                username_elements = item.find_elements(By.XPATH, ".//a[contains(@href, '/user/')]//span/span/span/span/span[string-length(text()) > 0]")
                                if username_elements:
                                    username = username_elements[0].text.strip()
                                    logger.info(f"找到用户名: {username}")
                            except Exception as e:
                                logger.debug(f"提取用户名失败: {str(e)}")
                                
                            if not username:
                                username = "未知用户"
                                logger.warning("未能获取用户名,使用默认值")
                                
                            # 提取用户ID - 使用链接href
                            user_id = None
                            try:
                                link_elements = item.find_elements(By.XPATH, ".//a[contains(@href, '/user/')]")
                                if link_elements:
                                    href = link_elements[0].get_attribute('href')
                                    if href and '/user/' in href:
                                        user_id = href.split('/user/')[-1].split('?')[0]
                                        logger.info(f"从链接提取用户ID: {user_id}")
                            except Exception as e:
                                logger.warning(f"提取用户ID失败: {str(e)}")
                                
                            if not user_id:
                                user_id = f"temp_{int(time.time())}_{random.randint(1000, 9999)}"
                                logger.warning(f"未能获取用户ID,使用临时ID: {user_id}")
                                
                            # 点击关注按钮
                            logger.info(f"准备关注用户: {username} ({user_id})")
                            follow_button.click()
                            self.random_sleep(2, 3)  # 增加等待时间
                            
                    except Exception as e:
                        logger.warning(f"处理用户项失败: {str(e)}")
                        continue
            else:
                logger.warning("未在弹窗中找到任何用户项")
            
            # 关闭弹窗
            try:
                # 使用DOM结构和按钮属性定位关闭按钮
                close_button_selectors = [
                    ".//button[@aria-label='Close']",  # 使用aria-label属性
                    ".//button[contains(@class, 'semi-modal-close')]",  # 基于semi-modal结构
                    ".//button[.//span[contains(text(), '取消')]]"  # 基于按钮文本
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
                
                # 如果没有找到关闭按钮,尝试使用ESC键
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
            logger.info(f"准备取消关注用户: {user_id} ({username})")
            
            # 保存操作前的截图
            save_screenshot(self.driver, f"unfollow_{user_id}_before", level="NORMAL")
            
            # 查找已关注按钮 - 使用data-e2e属性精确定位
            followed_button_selectors = [
                "//button[@data-e2e='user-info-follow-btn']"  # 使用您提供的data-e2e属性
            ]
            
            followed_btn = None
            for selector in followed_button_selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, selector)
                    if buttons:
                        for button in buttons:
                            if button.is_displayed():
                                button_text = button.text.strip()
                                if "已关注" in button_text or "互相关注" in button_text:
                                    followed_btn = button
                                    logger.info(f"找到已关注按钮，使用选择器: {selector}")
                                    break
                    if followed_btn:
                        break
                except Exception as e:
                    logger.warning(f"使用选择器 {selector} 查找按钮时出错: {str(e)}")
                    continue
            
            if not followed_btn:
                logger.warning(f"未找到已关注按钮: {user_id}")
                save_screenshot(self.driver, f"unfollow_{user_id}_not_found", level="ERROR")
                return False
            
            # 记录按钮文本和类名，便于调试
            try:
                button_text = followed_btn.text.strip()
                button_class = followed_btn.get_attribute("class")
                logger.info(f"已关注按钮文本: '{button_text}', 类名: '{button_class}'")
            except:
                logger.warning("无法获取按钮文本或类名")
            
            # 点击已关注按钮
            try:
                logger.info("尝试直接点击已关注按钮")
                followed_btn.click()
                self.random_sleep(2, 3)  # 等待按钮状态变化
            except Exception as e:
                logger.warning(f"直接点击已关注按钮失败: {str(e)}，尝试使用JavaScript点击")
                try:
                    self.driver.execute_script("arguments[0].click();", followed_btn)
                    self.random_sleep(2, 3)  # 等待按钮状态变化
                except Exception as js_e:
                    logger.error(f"JavaScript点击已关注按钮也失败: {str(js_e)}")
                    save_screenshot(self.driver, f"unfollow_{user_id}_click_failed", level="ERROR")
                    return False
            
            # 验证取关是否成功 - 检查按钮是否变成了"关注"
            try:
                # 重新查找按钮
                follow_btn = self.driver.find_element(By.XPATH, "//button[@data-e2e='user-info-follow-btn']")
                follow_btn_text = follow_btn.text.strip()
                follow_btn_class = follow_btn.get_attribute("class")
                
                logger.info(f"点击后按钮文本: '{follow_btn_text}', 类名: '{follow_btn_class}'")
                
                # 判断是否成功取关 - 按钮文本变为"关注"
                if "关注" == follow_btn_text and "已关注" not in follow_btn_text and "互相关注" not in follow_btn_text:
                    logger.info(f"取关成功，按钮已变为 '{follow_btn_text}'")
                    # 保存操作后的截图
                    save_screenshot(self.driver, f"unfollow_{user_id}_after", level="NORMAL")
                    
                    # 更新数据库
                    self.db.remove_follow_record(user_id)
                    logger.info(f"成功取消关注用户: {user_id} ({username})")
                    return True
                else:
                    logger.warning(f"取关失败，按钮文本为 '{follow_btn_text}'，未变为'关注'")
                    save_screenshot(self.driver, f"unfollow_{user_id}_failed", level="ERROR")
                    return False
            except Exception as e:
                logger.error(f"验证取关结果时出错: {str(e)}")
                save_screenshot(self.driver, f"unfollow_{user_id}_verify_error", level="ERROR")
                return False
            
        except Exception as e:
            logger.error(f"取消关注用户失败: {user_id} ({username}), 错误: {str(e)}")
            # 保存错误截图
            save_screenshot(self.driver, f"unfollow_{user_id}_error", level="ERROR")
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
                    "//div[@data-e2e='user-fans-container']",  # 使用data-e2e属性
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
                
                # 使用HTML层级结构和语义化属性定义用户项选择器
                user_item_selectors = [
                    # 基于data-e2e属性和DOM结构
                    ".//div[@data-e2e='user-fans-container']/div/div[.//a[contains(@href, '/user/')] and .//button[@data-e2e='user-info-follow-btn']]",
                    # 基于DOM层级和结构关系
                    ".//div[.//a[contains(@href, '/user/')] and .//button[contains(@class, 'semi-button')] and .//div[contains(@class, 'avatar-component')]]",
                    # 基于完整的DOM结构
                    ".//div[.//span[@data-e2e='live-avatar'] and .//button[contains(@class, 'semi-button')]]"
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
                
                # 用户名选择器 - 基于DOM层级结构
                username_selectors = [
                    # 基于data-e2e属性和DOM层级
                    ".//a[contains(@href, '/user/')]//span[@data-e2e='user-name']",
                    # 基于DOM层级结构
                    ".//a[contains(@href, '/user/')]//span[not(@role) and string-length(text()) > 0]",
                    # 基于avatar和用户名的关系
                    ".//span[@data-e2e='live-avatar']/following-sibling::div//a[contains(@href, '/user/')]//span[string-length(text()) > 0]"
                ]
                
                # 关注状态选择器 - 基于data-e2e属性和DOM结构
                follow_status_selectors = [
                    # 基于data-e2e属性
                    ".//button[@data-e2e='user-info-follow-btn']",
                    # 基于semi-button组件结构
                    ".//button[contains(@class, 'semi-button')]//div[contains(@class, 'semi-button-content')]",
                    # 基于按钮和文本的层级关系
                    ".//button[contains(@class, 'semi-button')]//div[string-length(text()) > 0]"
                ]
                
                # 用户ID选择器 - 基于href属性
                user_id_selectors = [
                    # 从用户链接中提取ID
                    ".//a[contains(@href, '/user/')]",
                    # 从头像链接中提取ID
                    ".//span[@data-e2e='live-avatar']/parent::a[contains(@href, '/user/')]"
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
                    user_items = popup_element.find_elements(By.XPATH, best_selector)
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
                                    for btn in follow_buttons:
                                        try:
                                            button_text = btn.text.strip()
                                            # 根据按钮文本判断关注状态
                                            if "相互关注" in button_text:
                                                follow_status = "mutual"
                                                break
                                            elif "已关注" in button_text:
                                                follow_status = "following"
                                                break
                                            elif "关注" in button_text:
                                                follow_status = "not_following"
                                                break
                                        except Exception as e:
                                            logger.debug(f"获取按钮文本失败: {str(e)}")
                                            continue
                                if follow_status:
                                    break
                            except Exception as e:
                                logger.debug(f"使用选择器 {selector} 获取关注状态失败: {str(e)}")
                        
                        # 如果状态未确定,默认为已关注
                        if not follow_status:
                            follow_status = "following"
                            logger.info(f"用户 {username} 的关注状态无法确定,默认为'following'")
                        
                        # 提取用户ID
                        user_id = None
                        for selector in user_id_selectors:
                            try:
                                link_elements = user_item.find_elements(By.XPATH, selector)
                                if link_elements:
                                    href = link_elements[0].get_attribute('href')
                                    if href and '/user/' in href:
                                        user_id = href.split('/user/')[-1].split('?')[0]
                                        break
                            except Exception as e:
                                logger.debug(f"使用选择器 {selector} 获取用户ID失败: {str(e)}")
                        
                        if not user_id:
                            user_id = f"temp_{int(time.time())}_{random.randint(1000, 9999)}"
                            logger.warning(f"无法获取用户ID,使用临时ID: {user_id}")
                        
                        # 添加到关注列表
                        follow_items.append({
                            "username": username,
                            "status": follow_status,
                            "user_id": user_id
                        })
                        
                        logger.info(f"处理用户: {username} ({user_id}), 关注状态: {follow_status}")
                    
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
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", last_user)
                            time.sleep(2)  # 增加等待时间确保加载
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

                        # 保存所有用户信息到数据库
                        saved_count = 0
                        updated_count = 0
                        for item in follow_items:
                            try:
                                if not item['user_id']:
                                    logger.warning(f"跳过保存用户 {item['username']}: 无效的用户ID")
                                    continue
                                    
                                # 检查用户是否已存在
                                try:
                                    user_exists = self.db.is_user_exists(item['user_id'])
                                except Exception as e:
                                    logger.error(f"检查用户是否存在失败: {item['username']} ({item['user_id']}), 错误: {str(e)}")
                                    continue
                                
                                # 根据关注状态设置from_fan参数
                                from_fan = 1 if "相互关注" in item['status'] else 0
                                
                                if not user_exists:
                                    # 新用户，添加到数据库
                                    try:
                                        self.db.add_follow_record(item['user_id'], item['username'], from_fan)
                                        saved_count += 1
                                        logger.info(f"新增用户到数据库: {item['username']} ({item['user_id']})")
                                    except Exception as e:
                                        logger.error(f"保存新用户失败: {item['username']}, 错误: {str(e)}")
                                else:
                                    # 已存在的用户，更新状态
                                    try:
                                        self.db.update_follow_status(item['user_id'], from_fan)
                                        updated_count += 1
                                        logger.info(f"更新用户关注状态: {item['username']} ({item['user_id']})")
                                    except Exception as e:
                                        logger.error(f"更新用户状态失败: {item['username']}, 错误: {str(e)}")
                            except Exception as e:
                                logger.error(f"处理用户信息失败: {item['username']}, 错误: {str(e)}")
                                
                        logger.info(f"数据库操作统计: 新增 {saved_count} 个用户, 更新 {updated_count} 个用户")
                        
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
                                        if not user['user_id']:
                                            logger.warning(f"跳过标记用户 {user['username']}: 无效的用户ID")
                                            continue
                                            
                                        # 检查用户是否已存在
                                        try:
                                            user_exists = self.db.is_user_exists(user['user_id'])
                                        except Exception as e:
                                            logger.error(f"检查用户是否存在失败: {user['username']} ({user['user_id']}), 错误: {str(e)}")
                                            continue
                                            
                                        if not user_exists:
                                            logger.warning(f"跳过标记用户 {user['username']}: 用户不存在于数据库")
                                            continue
                                            
                                        # 获取取关天数阈值
                                        unfollow_days = self.config.get('operation', {}).get('follow_list_tasks', {}).get('unfollow_days', 3)
                                        if self.db.mark_user_for_unfollow(user['user_id'], user['username'], unfollow_days):
                                            marked_count += 1
                                            logger.info(f"标记用户为待取关: {user['username']} ({user['user_id']})")
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