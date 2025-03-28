"""
关注管理模块

该模块提供了关注和取消关注用户的功能。
"""

from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    NoSuchElementException,
    TimeoutException
)
import time
import random
import sys
from .logger import logger, save_screenshot, save_html
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import re
from .user_info_utils import UserInfoUtils

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
        # 初始化用户信息工具类
        self.user_info_utils = UserInfoUtils(self.driver, self.wait, self.random_sleep)
            
    def run_check_follows_task(self):
        """
        执行检查关注列表任务
        
        该任务会检查当前账号的关注列表，找出未回关的用户，并标记为待取关
        """
        try:
            logger.info("开始执行检查关注列表任务...")
            
            # 打开用户主页
            self.driver.get("https://www.douyin.com/user/self")
            self.random_sleep(3, 5)
            
            # 点击关注按钮打开关注列表
            logger.info("点击关注按钮打开关注列表...")
            try:
                # 定位到data-e2e='user-info-follow'下包含"关注"文本的元素
                follow_button = self.driver.find_element(By.XPATH, "//div[@data-e2e='user-info-follow']//div[text()='关注']")
                follow_button.click()
                self.random_sleep(2, 3)
            except Exception as e:
                logger.error(f"点击关注按钮失败: {str(e)}")
                self.handle_task_failure("点击关注按钮失败", e, "check_follows_button_error")
                return False
            
            # 获取关注列表容器
            container = None
            container_selectors = [
                "//div[@data-e2e='user-fans-container']",  # 使用data-e2e属性
                "//div[contains(@class, 'scroll-content')]"  # 备用选择器
            ]
            
            for selector in container_selectors:
                try:
                    containers = self.driver.find_elements(By.XPATH, selector)
                    if containers:
                        container = containers[0]
                        logger.info(f"找到关注列表容器: {selector}")
                        break
                except Exception as e:
                    continue
            
            if not container:
                logger.error("未找到关注列表容器")
                return False
            
            # 获取关注总数
            total_follows = 0
            try:
                total_text = self.driver.find_element(By.XPATH, "//div[contains(@class, 'tab-active')]").text
                match = re.search(r'关注\s*\(?(\d+)\)?', total_text)
                if match:
                    total_follows = int(match.group(1))
                    logger.info(f"获取到关注总数: {total_follows}")
            except Exception as e:
                logger.warning(f"获取关注总数失败: {str(e)}")
            
            # 保存页面截图和源码，用于分析
            save_screenshot(self.driver, "follows_page", level="NORMAL")
            save_html(self.driver, "follows_page")
            
            # 使用UserInfoUtils滚动并提取用户信息
            users_info, success = self.user_info_utils.scroll_and_extract_users(
                container, 
                "关注列表", 
                expected_total=total_follows,
                max_no_new_content=3,
                min_wait=2,
                max_wait=3,
                max_retries=3
            )
            
            if not success:
                logger.warning("滚动并提取用户信息失败")
                return False
            
            # 处理提取到的用户信息
            if users_info:
                # 统计关注情况
                total_users = len(users_info)
                mutual_follows = sum(1 for user in users_info if user['follow_status'] == "mutual")
                non_mutual_follows = sum(1 for user in users_info if user['follow_status'] == "following")
                
                logger.info(f"关注列表统计: 总关注 {total_users}, 互相关注 {mutual_follows}, 未回关 {non_mutual_follows}")
                
                # 保存用户信息到数据库
                saved_count = 0
                updated_count = 0
                current_count = 0  # 当前处理的用户序号
                
                for user_info in users_info:
                    current_count += 1
                    try:
                        # 检查用户是否已存在
                        user_exists = self.db.is_user_exists(user_info['user_id'])
                        
                        # 根据关注状态设置from_fan参数
                        from_fan = 1 if user_info['follow_status'] == "mutual" else 0
                        
                        if not user_exists:
                            # 新用户，添加到数据库
                            logger.info(f"[{current_count}/{total_users}] 添加新关注用户到数据库: {user_info['username']} ({user_info['user_id']}), 互相关注: {from_fan == 1}")
                            self.db.add_follow_record(user_info['user_id'], user_info['username'], from_fan)
                            saved_count += 1
                        else:
                            # 已存在的用户，更新状态
                            logger.info(f"[{current_count}/{total_users}] 更新已存在用户的关注状态: {user_info['username']} ({user_info['user_id']}), 互相关注: {from_fan == 1}")
                            self.db.update_follow_status(user_info['user_id'], from_fan)
                            updated_count += 1
                            
                    except Exception as e:
                        logger.error(f"[{current_count}/{total_users}] 处理用户信息失败: {user_info['username']}, 错误: {str(e)}")
                
                logger.info(f"数据库操作统计: 新增 {saved_count}/{total_users} 个用户, 更新 {updated_count}/{total_users} 个用户")
                
                # 标记未回关的用户为待取关
                non_mutual_users = [user for user in users_info if user['follow_status'] == "following"]
                if non_mutual_users:
                    marked_count = 0
                    unfollow_days = self.config.get('operation', {}).get('follow_list_tasks', {}).get('unfollow_days', 3)
                    current_non_mutual = 0  # 当前处理的未回关用户序号
                    total_non_mutual = len(non_mutual_users)  # 总未回关用户数
                    
                    for user in non_mutual_users:
                        current_non_mutual += 1
                        try:
                            if self.db.mark_user_for_unfollow(user['user_id'], user['username'], unfollow_days):
                                marked_count += 1
                                logger.info(f"[{current_non_mutual}/{total_non_mutual}] 已标记用户 {user['username']} ({user['user_id']}) 为待取关，将在 {unfollow_days} 天后取关")
                            else:
                                logger.warning(f"[{current_non_mutual}/{total_non_mutual}] 标记用户 {user['username']} 为待取关失败")
                        except Exception as e:
                            logger.error(f"[{current_non_mutual}/{total_non_mutual}] 标记用户为待取关失败: {user['username']}, 错误: {str(e)}")
                            
                    logger.info(f"已标记 {marked_count}/{total_non_mutual} 个用户为待取关")
                
                    return True
                else:
                    logger.warning("未获取到任何关注用户信息")
                    return False
            
        except Exception as e:
            logger.error(f"检查关注列表任务失败: {str(e)}")
            self.handle_task_failure("检查关注列表任务失败", e, "check_follows_error")
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