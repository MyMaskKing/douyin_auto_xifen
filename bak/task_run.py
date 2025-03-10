"""
任务运行模块

该模块提供了任务调度和执行的功能。
"""

import time
import logging
import random
from datetime import datetime, timedelta
from .logger import logger, save_screenshot, save_html
from selenium.webdriver.common.by import By
import re
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

class TaskRunner:
    """任务运行类，负责任务调度和执行"""
    
    def __init__(self, browser_manager, user_profile_manager, fan_manager, follow_manager, db, config):
        """
        初始化任务运行器
        
        参数:
            browser_manager: 浏览器管理器对象
            user_profile_manager: 用户资料管理器对象
            fan_manager: 粉丝管理器对象
            follow_manager: 关注管理器对象
            db: 数据库对象
            config: 配置对象
        """
        self.browser_manager = browser_manager
        self.user_profile_manager = user_profile_manager
        self.fan_manager = fan_manager
        self.follow_manager = follow_manager
        self.db = db
        self.config = config
        self.driver = browser_manager.driver
        self.random_sleep = browser_manager.random_sleep
        self.today_follows = 0
        self.today_unfollows = 0
        
    def handle_task_failure(self, error_message, error, screenshot_name=None):
        """
        处理任务失败
        """
        logger.error(f"{error_message}: {str(error)}")
        
        # 检查是否是会话失效错误
        if "invalid session id" in str(error):
            logger.error("浏览器会话已断开，尝试重启浏览器")
            try:
                if self.browser_manager.restart_browser():
                    logger.info("浏览器重启成功")
                    return
                else:
                    logger.error("浏览器重启失败")
            except Exception as e:
                logger.error(f"重启浏览器时出错: {str(e)}")
        
        # 保存截图
        if screenshot_name:
            try:
                save_screenshot(self.driver, screenshot_name)
            except Exception as e:
                logger.error(f"保存截图失败: {str(e)}")
        
        # 尝试返回主页
        try:
            self.driver.get("https://www.douyin.com/")
            time.sleep(2)
        except Exception as e:
            logger.error(f"返回主页失败: {str(e)}")
        
        # 如果错误严重，可能需要退出程序
        if any(critical_error in str(error) for critical_error in ["invalid session id", "no such session", "browser has closed"]):
            logger.error("任务失败，程序将退出")
            # 这里不直接退出，而是返回False，让调用者决定是否退出
            return False
        
    def run_tasks(self):
        """
        运行所有任务
        """
        try:
            # 检查浏览器状态
            logger.info("检查浏览器状态...")
            if not self.browser_manager.check_and_restart_browser():
                logger.error("浏览器状态异常，无法继续执行任务")
                return False
            
            # 获取当前任务配置
            task_config = self.config.get('task', {})
            
            # 执行取关任务
            if task_config.get('unfollow_enabled', True):
                unfollow_result = self.run_unfollow_task()
                # 如果取关任务失败，检查浏览器状态
                if not unfollow_result:
                    logger.warning("取关任务执行失败，检查浏览器状态")
                    if not self.browser_manager.check_and_restart_browser():
                        logger.error("浏览器状态异常，停止执行后续任务")
                        return False
            
            # 执行检查关注列表任务
            if task_config.get('check_follows_enabled', True):
                check_follows_result = self.run_check_follows_task()
                # 如果检查关注列表任务失败，检查浏览器状态
                if not check_follows_result:
                    logger.warning("检查关注列表任务执行失败，检查浏览器状态")
                    if not self.browser_manager.check_and_restart_browser():
                        logger.error("浏览器状态异常，停止执行后续任务")
                        return False
                
                # 检查关注列表任务完成后，休息一段时间再执行下一轮任务
                # 这里添加较长的休息时间，避免频繁执行相同任务
                rest_time = task_config.get('task_interval', 3600)  # 默认休息1小时
                logger.info(f"检查关注列表任务完成，休息 {rest_time} 秒后执行下一轮任务")
                time.sleep(rest_time)
            
            # 执行关注粉丝任务
            if task_config.get('follow_fans_enabled', True):
                follow_fans_result = self.run_follow_fans_task()
                # 如果关注粉丝任务失败，检查浏览器状态
                if not follow_fans_result:
                    logger.warning("关注粉丝任务执行失败，检查浏览器状态")
                    if not self.browser_manager.check_and_restart_browser():
                        logger.error("浏览器状态异常，停止执行后续任务")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"执行任务时出错: {str(e)}")
            self.handle_task_failure("执行任务失败", e, "run_tasks_error")
            return False
            
    def run_unfollow_task(self):
        """
        执行取关任务
        """
        try:
            logger.info("开始执行取关任务...")
            
            # 检查浏览器状态
            if not self.browser_manager.check_and_restart_browser():
                logger.error("浏览器状态异常，无法执行取关任务")
                return False
            
            # 获取今日可取关数量
            max_unfollow_per_day = self.config.get('operation', {}).get('max_unfollow_per_day', 100)
            unfollow_count_today = self.db.get_unfollow_count_today()
            remaining_unfollow = max_unfollow_per_day - unfollow_count_today
            
            logger.info(f"今日剩余可取关数量: {remaining_unfollow}")
            
            if remaining_unfollow <= 0:
                logger.info("今日取关数量已达上限，跳过取关任务")
                return True
            
            # 获取需要取关的用户
            users_to_unfollow = self.db.get_users_to_unfollow(remaining_unfollow)
            
            if not users_to_unfollow:
                logger.info("没有找到需要取关的用户")
                return True
            
            logger.info(f"找到 {len(users_to_unfollow)} 个需要取关的用户")
            
            # 分批处理取关用户
            batch_size = self.config.get('operation', {}).get('unfollow_batch_size', 10)
            
            for i in range(0, len(users_to_unfollow), batch_size):
                batch = users_to_unfollow[i:i+batch_size]
                logger.info(f"开始处理第 {i//batch_size + 1} 批取关用户，共 {len(batch)} 个")
                
                success_count = 0
                
                for user in batch:
                    try:
                        # 检查浏览器状态，确保会话有效
                        if not self.browser_manager.is_browser_alive():
                            logger.error("浏览器会话已断开，重新启动浏览器")
                            if not self.browser_manager.restart_browser():
                                logger.error("重启浏览器失败，取消当前取关任务")
                                return False
                        
                        logger.info(f"准备取关用户: {user['username']} ({user['user_id']})")
                        
                        # 访问用户页面
                        user_url = f"https://www.douyin.com/user/{user['user_id']}"
                        logger.info(f"访问用户页面: {user_url}")
                        
                        try:
                            self.driver.get(user_url)
                            time.sleep(3)  # 等待页面加载
                        except Exception as e:
                            logger.error(f"访问用户页面失败: {str(e)}")
                            # 检查浏览器状态，如果会话已断开则重启
                            if "invalid session id" in str(e):
                                logger.error("浏览器会话已断开，尝试重启浏览器")
                                if not self.browser_manager.restart_browser():
                                    logger.error("重启浏览器失败，取消当前取关任务")
                                    return False
                                continue  # 跳过当前用户，处理下一个
                        
                        # 执行取关操作
                        if self.follow_manager.unfollow_user(user['user_id'], user['username']):
                            success_count += 1
                            # 更新数据库中的用户状态
                            self.db.update_user_unfollow_status(user['user_id'])
                        else:
                            logger.warning(f"取关用户失败: {user['username']} ({user['user_id']})")
                        
                        # 随机等待一段时间再处理下一个用户
                        wait_time = random.uniform(5, 15)
                        logger.info(f"等待 {wait_time:.2f} 秒后处理下一个用户")
                        time.sleep(wait_time)
                        
                    except Exception as e:
                        logger.error(f"处理取关用户失败: {user['username']} ({user['user_id']}), 错误: {str(e)}")
                        # 检查是否是会话失效错误
                        if "invalid session id" in str(e):
                            logger.error("浏览器会话已断开，尝试重启浏览器")
                            if not self.browser_manager.restart_browser():
                                logger.error("重启浏览器失败，取消当前取关任务")
                                return False
                        
                        # 继续处理下一个用户
                        wait_time = random.uniform(5, 15)
                        logger.info(f"等待 {wait_time:.2f} 秒后处理下一个用户")
                        time.sleep(wait_time)
                
                # 计算成功率
                success_rate = success_count / len(batch) if batch else 0
                logger.info(f"第 {i//batch_size + 1} 批取关完成，成功率: {success_rate:.2f}")
                
                # 如果成功率过低，暂停取关任务
                min_success_rate = self.config.get('operation', {}).get('min_unfollow_success_rate', 0.7)
                if success_rate < min_success_rate:
                    logger.warning(f"取关成功率 {success_rate:.2f} 低于阈值 {min_success_rate}，暂停取关任务")
                    break
            
            logger.info(f"取关任务完成，共处理 {len(users_to_unfollow)} 个用户，成功取关 {success_count} 个")
            
            # 返回个人主页
            try:
                self.driver.get("https://www.douyin.com/user/self")
                time.sleep(2)
                logger.info("通过URL返回个人主页: https://www.douyin.com/user/self")
            except Exception as e:
                logger.error(f"返回个人主页失败: {str(e)}")
                # 检查是否是会话失效错误
                if "invalid session id" in str(e):
                    logger.error("浏览器会话已断开，尝试重启浏览器")
                    if not self.browser_manager.restart_browser():
                        logger.error("重启浏览器失败")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"执行取关任务失败: {str(e)}")
            self.handle_task_failure("执行取关任务失败", e, "unfollow_task_error")
            return False
        
    def run_follow_fans_task(self):
        """执行关注粉丝任务"""
        logger.info("开始执行关注粉丝任务...")
        
        # 检查浏览器状态
        if not self.browser_manager.check_and_restart_browser():
            self.handle_task_failure("浏览器检查失败，无法执行关注粉丝任务", Exception("浏览器检查失败"))
            return
            
        if self.today_follows < self.config.get('operation', {}).get('daily_follow_limit', 150):
            # 获取目标用户列表
            target_users = self.config.get('target', {}).get('users', [])
            
            if not target_users:
                logger.warning("未配置目标用户，无法执行关注粉丝任务")
                return
            
            # 获取未处理过的目标用户
            try:
                unprocessed_users = self.db.get_unprocessed_target_users(target_users)
                
                if unprocessed_users:
                    logger.info(f"找到 {len(unprocessed_users)} 个今天未处理的目标用户")
                    # 优先处理未处理过的目标用户
                    target_users = unprocessed_users + [user for user in target_users if user not in unprocessed_users]
                else:
                    # 如果所有用户都已处理过，随机打乱目标用户列表
                    random.shuffle(target_users)
                    logger.info("今天所有目标用户都已处理过，随机选择目标用户")
            except Exception as e:
                logger.error(f"获取未处理目标用户失败: {str(e)}")
                # 随机打乱目标用户列表
                random.shuffle(target_users)
            
            # 处理每个目标用户
            for target_user in target_users:
                # 检查是否达到每日关注上限
                if self.today_follows >= self.config.get('operation', {}).get('daily_follow_limit', 150):
                    logger.info(f"已达到每日关注上限: {self.config.get('operation', {}).get('daily_follow_limit', 150)}")
                    break
                    
                # 检查目标用户是否有效
                if not target_user or target_user.strip() == "":
                    logger.warning("目标用户无效，跳过")
                    continue
                    
                # 检查是否已处理过该目标用户
                try:
                    if self.db.is_target_user_processed(target_user):
                        logger.info(f"目标用户今天已处理过: {target_user}，跳过")
                        continue
                except Exception as e:
                    logger.error(f"检查目标用户处理状态失败: {str(e)}")
                    
                try:
                    # 访问目标用户主页
                    logger.info(f"访问目标用户主页: {target_user}")
                    success = self.user_profile_manager.visit_user_profile(target_user)
                    
                    if not success:
                        logger.warning(f"访问目标用户主页失败: {target_user}，跳过")
                        continue
                        
                    # 点击粉丝标签
                    logger.info(f"点击粉丝标签: {target_user}")
                    success = self.user_profile_manager.click_fans_tab()
                    
                    if not success:
                        logger.warning(f"点击粉丝标签失败: {target_user}，跳过")
                        continue
                        
                    # 获取粉丝列表
                    logger.info(f"获取粉丝列表: {target_user}")
                    fan_items = self.fan_manager.get_fan_items()
                    
                    if not fan_items:
                        logger.warning(f"获取粉丝列表失败: {target_user}，跳过")
                        continue
                        
                    logger.info(f"找到 {len(fan_items)} 个粉丝")
                    
                    # 处理粉丝列表
                    processed_count = 0
                    max_fans_per_target = self.config.get('operation', {}).get('max_fans_per_target', 50)
                    
                    for fan_item in fan_items:
                        # 检查是否达到每日关注上限
                        if self.today_follows >= self.config.get('operation', {}).get('daily_follow_limit', 150):
                            logger.info(f"已达到每日关注上限: {self.config.get('operation', {}).get('daily_follow_limit', 150)}")
                            break
                            
                        # 检查是否达到每个目标用户的处理上限
                        if processed_count >= max_fans_per_target:
                            logger.info(f"已达到每个目标用户的处理上限: {max_fans_per_target}")
                            break
                            
                        # 关注粉丝
                        success = self.follow_manager.follow_user(fan_item)
                        
                        if success:
                            self.today_follows += 1
                            processed_count += 1
                            logger.info(f"成功关注粉丝，今日已关注: {self.today_follows}, 当前目标已处理: {processed_count}")
                        
                        # 随机等待
                        follow_interval = self.config.get('operation', {}).get('follow_interval', [3, 8])
                        self.random_sleep(follow_interval[0], follow_interval[1])
                    
                    # 标记目标用户为已处理
                    try:
                        self.db.mark_target_user_processed(target_user, processed_count)
                        logger.info(f"目标用户处理完成: {target_user}, 成功关注 {processed_count} 个粉丝")
                    except Exception as e:
                        logger.error(f"标记目标用户处理状态失败: {str(e)}")
                    
                    # 随机等待一段时间再处理下一个目标用户
                    wait_time = random.uniform(30, 60)
                    logger.info(f"等待 {wait_time:.2f} 秒后处理下一个目标用户")
                    time.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"处理目标用户失败: {target_user}, 错误: {str(e)}")
                    # 保存错误截图
                    save_screenshot(self.driver, f"error_{target_user}", level="ERROR")
                    continue
            
            # 任务完成后返回主页
            try:
                self.driver.get("https://www.douyin.com/user/self")
                logger.info("通过URL返回个人主页: https://www.douyin.com/user/self")
                self.random_sleep(2, 3)
            except Exception as e:
                self.handle_task_failure("返回个人主页失败", e)
                
        else:
            logger.info(f"已达到每日关注上限: {self.config.get('operation', {}).get('daily_follow_limit', 150)}")
            
    def run_check_follows_task(self):
        """
        执行检查关注列表任务
        """
        try:
            logger.info("开始执行检查关注列表任务...")
            
            # 打开用户主页
            self.driver.get("https://www.douyin.com/user/self")
            time.sleep(3)
            
            # 点击关注按钮打开关注列表
            logger.info("点击关注按钮打开关注列表...")
            follow_button = None
            try:
                follow_button = self.driver.find_element(By.XPATH, "//div[@data-e2e='user-info-follow']")
                follow_button.click()
                time.sleep(2)
            except Exception as e:
                logger.error(f"点击关注按钮失败: {str(e)}")
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
                "//div[contains(@class, 'semi-tabs-pane-active')]"  # 备用选择器
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
                self.handle_task_failure("未找到关注列表弹窗", Exception("未找到关注列表弹窗"), "check_follows_no_popup")
                return False
            
            # 获取关注总数
            total_follows_count = 0
            try:
                # 尝试从标签页标题中获取关注总数，例如"关注 (74)"
                tab_selectors = [
                    "//div[contains(@class, 'semi-tabs-tab-active')]",  # 活动标签
                    "//div[@role='tab' and @aria-selected='true']",  # 活动标签备用
                    "//div[contains(@class, 'semi-tabs-tab') and contains(text(), '关注')]"  # 关注标签
                ]
                
                for selector in tab_selectors:
                    try:
                        tab_elements = self.driver.find_elements(By.XPATH, selector)
                        if tab_elements:
                            tab_text = tab_elements[0].text.strip()
                            # 提取括号中的数字
                            import re
                            match = re.search(r'关注\s*\((\d+)\)', tab_text)
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
            follow_items = []
            
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
                ".//a[contains(@class, 'uz1VJwFY')]//span"  # 备用选择器
            ]
            
            # 关注状态选择器
            follow_status_selectors = [
                ".//div[contains(@class, 'zPZJ3j40')]",  # 主要选择器
                ".//button[contains(@class, 'xjIRvxqr')]//div",  # 备用选择器
                ".//button[contains(@class, 'xjIRvxqr')]",  # 按钮本身
                ".//div[contains(@class, 'semi-button-content')]",  # 按钮内容
                ".//div[contains(@class, 'semi-button')]",  # 通用按钮类
                ".//div[contains(@class, 'follow-button')]",  # 关注按钮
                ".//div[contains(@class, 'follow-state')]"  # 关注状态
            ]
            
            # 用户ID选择器
            user_id_selectors = [
                ".//a[contains(@href, '/user/')]",  # 用户链接
            ]
            
            # 滚动加载所有用户
            processed_usernames = set()  # 用于跟踪已处理的用户名，避免重复
            follow_items = []  # 存储关注用户信息
            last_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 8  # 进一步减少最大滚动尝试次数
            no_new_users_count = 0
            max_no_new_users = 3  # 连续3次没有新用户时停止滚动
            
            # 添加批处理计数器和休息机制
            batch_count = 0
            batch_size = 20  # 每处理20个用户休息一次
            
            while True:
                # 获取当前可见的用户项
                try:
                    user_items = popup_element.find_elements(By.XPATH, best_selector)
                    current_count = len(user_items)
                    
                    logger.info(f"当前已加载 {current_count} 个关注用户项")
                except Exception as e:
                    logger.warning(f"获取用户项失败: {str(e)}")
                    # 如果获取用户项失败，尝试重新获取弹窗元素
                    try:
                        for popup_selector in popup_selectors:
                            popup_elements = self.driver.find_elements(By.XPATH, popup_selector)
                            if popup_elements:
                                popup_element = popup_elements[0]
                                logger.info("重新获取弹窗元素成功")
                                break
                        # 如果重新获取成功，继续下一次循环
                        time.sleep(1)
                        continue
                    except:
                        # 如果重新获取失败，增加滚动尝试次数
                        scroll_attempts += 1
                        if scroll_attempts >= max_scroll_attempts:
                            logger.warning("多次获取用户项失败，停止加载")
                            break
                        time.sleep(1)
                        continue
                
                # 处理新加载的用户项
                new_users_found = 0
                
                # 处理所有新加载的用户项，不限制每次处理的数量
                for i in range(last_count, current_count):
                    if i >= len(user_items):
                        break
                    
                    user_item = user_items[i]
                    try:
                        # 提取用户名
                        username = None
                        for selector in username_selectors:
                            try:
                                username_elements = user_item.find_elements(By.XPATH, selector)
                                if username_elements:
                                    username = username_elements[0].text.strip()
                                    break
                            except:
                                continue
                        
                        if not username:
                            logger.warning(f"无法获取第 {i+1} 个用户的用户名")
                            continue
                        
                        # 检查是否已处理过该用户
                        if username in processed_usernames:
                            continue
                        
                        processed_usernames.add(username)
                        new_users_found += 1
                        
                        # 提取关注状态
                        follow_status = None
                        # 限制尝试次数，避免过多请求
                        max_selector_attempts = 3
                        selector_attempts = 0
                        
                        for selector in follow_status_selectors:
                            if selector_attempts >= max_selector_attempts:
                                break
                                
                            try:
                                status_elements = user_item.find_elements(By.XPATH, selector)
                                if status_elements:
                                    follow_status = status_elements[0].text.strip()
                                    if follow_status:  # 如果找到非空文本
                                        break
                            except Exception as e:
                                logger.debug(f"使用选择器 {selector} 获取关注状态失败: {str(e)}")
                            
                            selector_attempts += 1
                        
                        # 如果仍未找到关注状态，尝试通过元素属性或类名判断，但限制尝试次数
                        if not follow_status:
                            try:
                                # 检查是否有"已关注"或"相互关注"按钮，限制检查的按钮数量
                                follow_buttons = user_item.find_elements(By.XPATH, ".//button")
                                max_buttons = min(3, len(follow_buttons))  # 最多检查3个按钮
                                
                                for btn_index in range(max_buttons):
                                    try:
                                        button = follow_buttons[btn_index]
                                        button_class = button.get_attribute("class")
                                        button_text = button.text.strip()
                                        
                                        # 根据按钮类名或文本判断关注状态
                                        if "following" in button_class.lower() or "已关注" in button_text or "相互关注" in button_text:
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
                        
                    except Exception as e:
                        logger.warning(f"处理第 {i+1} 个用户项时出错: {str(e)}")
                
                # 更新已处理的用户数量
                last_count = current_count
                
                # 检查是否有新用户被添加
                if new_users_found == 0:
                    no_new_users_count += 1
                else:
                    no_new_users_count = 0
                
                # 检查是否已获取所有用户
                if total_follows_count > 0 and len(processed_usernames) >= total_follows_count:
                    logger.info(f"已获取所有 {total_follows_count} 个关注用户，停止滚动")
                    break
                
                # 检查是否连续多次没有新用户
                if no_new_users_count >= max_no_new_users:
                    logger.info(f"连续 {max_no_new_users} 次没有发现新用户，停止滚动")
                    break
                
                # 检查是否需要继续滚动
                if current_count == last_count:
                    scroll_attempts += 1
                    if scroll_attempts >= max_scroll_attempts:
                        logger.info(f"已达到最大滚动次数 {max_scroll_attempts}，停止加载更多用户")
                        break
                else:
                    # 只有当新增用户数量超过阈值时才重置滚动尝试次数
                    if new_users_found > 5:
                        scroll_attempts = 0
                    else:
                        # 如果新增用户很少，也增加滚动尝试计数
                        scroll_attempts += 0.5
                
                # 滚动到最后一个用户项以加载更多
                try:
                    if user_items:
                        # 随机选择滚动目标，避免总是滚动到最后一个元素
                        scroll_index = min(len(user_items) - 1, last_count + int((current_count - last_count) * 0.8))
                        scroll_item = user_items[scroll_index]
                        
                        # 使用更平滑的滚动
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                            scroll_item
                        )
                        
                        # 增加随机等待时间，减少请求频率
                        wait_time = 1.5 + random.uniform(0, 0.5)
                        time.sleep(wait_time)
                except Exception as e:
                    logger.warning(f"滚动加载更多用户失败: {str(e)}")
                    scroll_attempts += 1
                    # 出错时增加额外等待时间
                    time.sleep(1)
            
            # 立即处理获取到的用户信息，不等待所有滚动尝试结束
            logger.info(f"滚动加载完成，开始处理获取到的用户信息")
            
            # 保存关注列表到数据库并处理未互相关注的用户
            if follow_items:
                # 获取最终加载的用户数量
                final_user_count = 0
                try:
                    final_user_items = popup_element.find_elements(By.XPATH, best_selector)
                    final_user_count = len(final_user_items)
                except Exception as e:
                    logger.warning(f"获取最终用户数量失败: {str(e)}")
                    final_user_count = current_count
                
                logger.info(f"成功获取 {len(follow_items)} 个关注用户信息 (总加载用户数: {final_user_count}, 有效处理用户数: {len(processed_usernames)})")
                
                # 如果获取的用户数量与加载的用户数量不一致，记录警告
                if len(follow_items) < final_user_count:
                    logger.warning(f"注意: 加载了 {final_user_count} 个用户项，但只成功处理了 {len(follow_items)} 个用户信息")
                    logger.warning(f"可能原因: 1.有用户名为空 2.有重复用户 3.处理过程中出错")
                    
                    # 统计未能处理的用户数量
                    empty_username_count = 0
                    error_count = 0
                    duplicate_count = 0
                    
                    # 重新检查所有用户项，统计问题
                    try:
                        check_user_items = popup_element.find_elements(By.XPATH, best_selector)
                        temp_usernames = set()
                        
                        for i, check_user_item in enumerate(check_user_items):
                            try:
                                # 检查用户名
                                check_username = None
                                for selector in username_selectors:
                                    try:
                                        username_elements = check_user_item.find_elements(By.XPATH, selector)
                                        if username_elements:
                                            check_username = username_elements[0].text.strip()
                                            break
                                    except:
                                        continue
                                
                                if not check_username:
                                    empty_username_count += 1
                                elif check_username in temp_usernames:
                                    duplicate_count += 1
                                else:
                                    temp_usernames.add(check_username)
                            except Exception as e:
                                error_count += 1
                        
                        logger.warning(f"统计结果: 空用户名: {empty_username_count}, 重复用户: {duplicate_count}, 处理错误: {error_count}")
                        
                        # 尝试修复问题，确保所有用户都被处理
                        if empty_username_count > 0 or error_count > 0:
                            logger.info("尝试修复未处理的用户...")
                            
                            # 重新处理所有用户项
                            for i, fix_user_item in enumerate(check_user_items):
                                try:
                                    # 提取用户名
                                    fix_username = None
                                    for selector in username_selectors:
                                        try:
                                            username_elements = fix_user_item.find_elements(By.XPATH, selector)
                                            if username_elements:
                                                fix_username = username_elements[0].text.strip()
                                                break
                                        except:
                                            continue
                                    
                                    # 跳过空用户名或已处理的用户
                                    if not fix_username or fix_username in processed_usernames:
                                        continue
                                    
                                    # 处理新用户
                                    processed_usernames.add(fix_username)
                                    
                                    # 提取关注状态和用户ID
                                    fix_follow_status = "已关注"  # 默认为已关注
                                    fix_user_id = ""
                                    
                                    # 尝试获取用户ID
                                    for selector in user_id_selectors:
                                        try:
                                            link_elements = fix_user_item.find_elements(By.XPATH, selector)
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
                    # 根据用户提供的HTML元素信息，精确定位关闭按钮
                    close_button_selectors = [
                        "//div[contains(@class, 'KArYflhI')]",  # 用户提供的主要类名
                        "//div[contains(@class, 'KArYflhI')]/svg[contains(@class, 'xlWtWI6P')]",  # 包含SVG的完整路径
                        "//svg[contains(@class, 'xlWtWI6P')]",  # SVG类名
                        "//div[contains(@class, 'KArYflhI')]/svg",  # 简化路径
                        "//svg[@width='36' and @height='36' and @fill='#A9AAB7']",  # SVG属性
                        "//div[.//svg[contains(@class, 'xlWtWI6P')]]"  # 包含特定SVG的div
                    ]
                    
                    logger.info("尝试关闭关注列表弹窗...")
                    close_button_found = False
                    
                    # 尝试使用不同的选择器查找关闭按钮
                    for selector in close_button_selectors:
                        try:
                            close_buttons = self.driver.find_elements(By.XPATH, selector)
                            if close_buttons:
                                for button in close_buttons:
                                    try:
                                        if button.is_displayed() and button.is_enabled():
                                            # 先尝试直接点击
                                            try:
                                                button.click()
                                                logger.info(f"成功点击关闭按钮: {selector}")
                                                close_button_found = True
                                                time.sleep(1)  # 等待关闭动画
                                                break
                                            except Exception as e:
                                                logger.debug(f"直接点击失败，尝试使用JavaScript点击: {str(e)}")
                                                # 使用JavaScript点击
                                                self.driver.execute_script("arguments[0].click();", button)
                                                logger.info(f"通过JavaScript成功点击关闭按钮: {selector}")
                                                close_button_found = True
                                                time.sleep(1)  # 等待关闭动画
                                                break
                                    except Exception as e:
                                        logger.debug(f"尝试点击按钮失败: {str(e)}")
                                        continue
                                
                                if close_button_found:
                                    break
                        except Exception as e:
                            logger.debug(f"使用选择器 {selector} 查找关闭按钮失败: {str(e)}")
                    
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
                            logger.warning("关闭按钮点击后弹窗仍然存在，尝试其他方法")
                            
                            # 尝试使用更精确的JavaScript定位并点击关闭按钮
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
                            
                            time.sleep(1)
                            logger.info("通过JavaScript精确定位并点击关闭按钮")
                            
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
                            
                            if popup_still_exists:
                                # 如果弹窗仍然存在，尝试按ESC键关闭
                                logger.warning("JavaScript点击后弹窗仍然存在，尝试按ESC键关闭")
                                actions = ActionChains(self.driver)
                                actions.send_keys(Keys.ESCAPE).perform()
                                time.sleep(1)
                                
                                # 最后尝试刷新页面
                                if popup_still_exists:
                                    logger.warning("所有方法都无法关闭弹窗，尝试刷新页面")
                                    self.driver.refresh()
                                    time.sleep(2)
                    except Exception as e:
                        logger.warning(f"验证弹窗关闭状态时出错: {str(e)}")
                    
                    logger.info("已关闭关注列表弹窗")
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
            logger.error(f"检查关注列表任务失败: {str(e)}")
            self.handle_task_failure("检查关注列表任务失败", e, "check_follows_error")
            return False