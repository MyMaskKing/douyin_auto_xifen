"""
粉丝管理模块

该模块提供了获取和处理粉丝列表的功能。
"""

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
from datetime import datetime, timedelta
from .logger import logger, save_screenshot, save_html, get_log_path
import json
import re
from .message_manager import MessageManager
from .user_info_utils import UserInfoUtils
import random

class FanManager:
    """粉丝管理类，负责获取和处理粉丝列表"""
    
    def __init__(self, browser_manager, user_profile_manager, db, config):
        """
        初始化粉丝管理器
        
        参数:
            browser_manager: 浏览器管理器对象
            user_profile_manager: 用户资料管理器对象
            db: 数据库对象
            config: 配置对象
        """
        self.browser_manager = browser_manager
        self.user_profile_manager = user_profile_manager
        self.db = db
        self.config = config
        self.driver = browser_manager.driver
        self.wait = browser_manager.wait
        self.random_sleep = browser_manager.random_sleep
        # 初始化消息管理器
        self.message_manager = MessageManager(browser_manager, db, config)
        # 初始化用户信息工具类
        self.user_info_utils = UserInfoUtils(self.driver, self.wait, self.random_sleep)

    def get_fan_items(self):
        """
        获取粉丝列表项
        
        返回:
            粉丝项列表，每项包含元素、按钮和名称
        """
        try:
            # 等待页面完全加载
            logger.info("等待页面完全加载...")
            self.random_sleep(3, 5)
            
            # 获取预期的粉丝总数
            expected_total = self.get_expected_total_fans()
            if not expected_total:
                logger.error("无法获取预期粉丝总数")
                return []
            
            logger.info(f"开始处理粉丝列表，预期总数: {expected_total}")
            
            # 保存页面截图和源码，用于分析
            save_screenshot(self.driver, "fans_page", level="NORMAL")
            save_html(self.driver, "fans_page")
            
            # 初始化结果
            result = []
            retry_count = 0
            max_retries = 3
            
            while True:
                try:
                    # 每次重新获取容器，避免stale element问题
                    container = None
                    container_selectors = [
                        "//div[@data-e2e='user-fans-container']",
                        "//div[contains(@class, 'FjupSA6k')]"
                    ]
                    
                    for selector in container_selectors:
                        try:
                            containers = self.driver.find_elements(By.XPATH, selector)
                            if containers:
                                container = containers[0]
                                break
                        except Exception as e:
                            continue
                    
                    if not container:
                        logger.error("未找到粉丝列表容器")
                        if retry_count < max_retries:
                            retry_count += 1
                            self.random_sleep(2, 3)
                            continue
                        else:
                            break
                    
                    # 使用UserInfoUtils滚动并提取用户信息
                    users_info, success = self.user_info_utils.scroll_and_extract_users(
                        container, 
                        "粉丝列表", 
                        expected_total=expected_total,
                        max_no_new_content=5,
                        min_wait=3,
                        max_wait=5,
                        max_retries=3
                    )
                    
                    if not success:
                        logger.warning("滚动并提取用户信息失败")
                        if retry_count < max_retries:
                            retry_count += 1
                            self.random_sleep(2, 3)
                            continue
                        else:
                            break
                    
                    # 处理提取到的用户信息
                    for user_info in users_info:
                        # 检查数据库中是否已存在该粉丝
                        existing_fan = self.db.get_user_by_id(user_info['user_id'])
                        
                        # 确定最终的关注状态
                        if existing_fan:
                            # 已存在的粉丝，使用数据库中的状态
                            db_follow_status = existing_fan.get('follow_status', 'unknown')
                            logger.info(f"用户 {user_info['username']} ({user_info['user_id']}) 在数据库中已存在，状态为: {db_follow_status}")
                            
                            # 只有当UI状态与数据库状态不一致时才更新
                            if user_info['follow_status'] != "unknown" and user_info['follow_status'] != db_follow_status:
                                logger.info(f"更新用户 {user_info['username']} 的关注状态: {db_follow_status} -> {user_info['follow_status']}")
                                self.db.add_fan_record(user_info['user_id'], user_info['username'], user_info['follow_status'])
                                follow_status = user_info['follow_status']
                            else:
                                follow_status = db_follow_status
                        else:
                            # 新发现的粉丝
                            logger.info(f"发现新粉丝: {user_info['username']} ({user_info['user_id']}), 状态: {user_info['follow_status']}")
                            if user_info['follow_status'] != "unknown":
                                follow_status = user_info['follow_status']
                            else:
                                # 默认为新粉丝
                                follow_status = "new_fan"
                            
                            # 将新粉丝信息保存到数据库
                            logger.info(f"将新粉丝 {user_info['username']} 添加到数据库，状态: {follow_status}")
                            self.db.add_fan_record(user_info['user_id'], user_info['username'], follow_status)
                        
                        # 添加到结果列表
                        result.append({
                            'element': user_info['element'],
                            'username': user_info['username'],
                            'user_id': user_info['user_id'],
                            'follow_status': follow_status,
                            'follow_back_button': user_info['button_element'] if user_info['button_type'] == 'follow' else None
                        })
                    
                    # 滚动和提取完成后，退出循环
                    break
                    
                except Exception as e:
                    logger.warning(f"处理粉丝列表过程中出错: {str(e)}")
                    if retry_count < max_retries:
                        retry_count += 1
                        self.random_sleep(2, 3)
                        continue
                    else:
                        break
            
            # 最终统计
            logger.info(f"粉丝列表处理完成，成功获取 {len(result)} 个粉丝信息，预期总数 {expected_total}")
            if len(result) < expected_total:
                logger.warning(f"未能获取全部粉丝信息，差距 {expected_total - len(result)} 个")
            
            return result
            
        except Exception as e:
            logger.error(f"获取粉丝列表项失败: {str(e)}")
            return []

    def get_expected_total_fans(self):
        """获取预期的粉丝总数"""
        try:
            # 使用固定的data-e2e属性选择器
            fans_button = self.driver.find_element(By.XPATH, "//div[@data-e2e='user-info-fans']")
            # 获取第二个div中的数字
            fans_count_element = fans_button.find_element(By.XPATH, './/div[2]')
            fans_text = fans_count_element.text.strip()
            logger.info(f"粉丝数量文本内容: {fans_text}")
            
            # 使用正则表达式提取数字
            numbers = re.findall(r'\d+', fans_text)
            if numbers:
                expected_total = int(numbers[0])
                # 处理单位（万、亿）
                if '万' in fans_text:
                    expected_total *= 10000
                elif '亿' in fans_text:
                    expected_total *= 100000000
                logger.info(f"预期粉丝总数: {expected_total}")
                return expected_total
            else:
                logger.warning(f"未在文本中找到数字: {fans_text}")
                return None
                
        except Exception as e:
            logger.warning(f"获取预期粉丝总数失败: {str(e)}")
            return None

    def run_check_fans_task(self):
        """
        执行检查粉丝列表任务
        
        功能：检查当前账号的粉丝列表，找出带有"回关"按钮的用户，并标记为待回关。
        
        参数说明：
        - check_fans_interval：配置文件中设置的检查粉丝列表的时间间隔（秒）。
        - max_fans_per_check：每次检查时处理的最大粉丝数量。
        
        返回：
        - 成功返回True，失败返回False。
        - 返回的数据包括已处理的粉丝数量和新标记的待回关用户数量。
        """
        try:
            logger.info("开始执行检查粉丝列表任务...")
            
            # 访问个人主页
            logger.info("访问个人主页...")
            self.driver.get("https://www.douyin.com/user/self")
            self.random_sleep(3, 5)
            
            # 点击粉丝标签
            logger.info("点击粉丝标签...")
            success, total_fans_count = self.user_profile_manager.click_fans_tab()
            self.random_sleep(3, 5)
            
            if not success:
                logger.error("点击粉丝标签失败")
                return False
                
            logger.info(f"粉丝总数: {total_fans_count}")
            
            # 获取并保存所有粉丝信息
            logger.info("开始获取并保存粉丝列表...")
            fan_items = self.get_fan_items()
            
            if not fan_items:
                logger.warning("未找到任何粉丝项")
                return False
            
            # 统计粉丝状态
            stats = self.calculate_fan_stats(fan_items)
            logger.info(f"粉丝统计: {stats}")
            
            # 处理需要回关的用户（只标记，不执行回关）
            if stats['need_follow_back'] > 0:
                logger.info(f"发现 {stats['need_follow_back']} 个需要回关的用户")
                self.process_follow_back_users(fan_items)
            else:
                logger.info("没有需要回关的用户")
            
            # 返回个人主页
            self.driver.get("https://www.douyin.com/user/self")
            self.random_sleep(2, 3)
            
            return True
        except Exception as e:
            logger.error(f"检查粉丝列表任务失败: {str(e)}")
            save_screenshot(self.driver, "fans_check_error")
            return False

    def calculate_fan_stats(self, fan_items):
        """计算粉丝统计信息"""
        stats = {
            'total': len(fan_items),
            'mutual': sum(1 for item in fan_items if item['follow_status'] == "mutual"),
            'need_follow_back': sum(1 for item in fan_items if item['follow_status'] == "need_follow_back"),
            'requested': sum(1 for item in fan_items if item['follow_status'] == "requested"),
            'new_fans': sum(1 for item in fan_items if item['follow_status'] == "new_fan")
        }
        return stats

    def process_follow_back_users(self, fan_items):
        """处理需要回关的用户"""
        need_follow_back_users = [item for item in fan_items if item['follow_status'] == "need_follow_back"]
        
        if not need_follow_back_users:
            logger.info("没有找到需要回关的用户")
            return
            
        logger.info(f"找到 {len(need_follow_back_users)} 个需要回关的用户")
        marked_count = 0
        
        # 批量处理
        batch_size = 10
        for i in range(0, len(need_follow_back_users), batch_size):
            batch = need_follow_back_users[i:i+batch_size]
            
            for user in batch:
                try:
                    if user['user_id'] and self.db.mark_user_for_follow_back(user['user_id'], user['username']):
                        marked_count += 1
                        logger.info(f"已标记用户 {user['username']} ({user['user_id']}) 为待回关")
                except Exception as e:
                    logger.error(f"标记用户为待回关失败: {user['username']}, 错误: {str(e)}")
            
            if i + batch_size < len(need_follow_back_users):
                time.sleep(0.5)
        
        logger.info(f"已标记 {marked_count} 个用户为待回关")

    def run_follow_back_task(self):
        """
        执行回关任务
        
        返回:
            成功返回True，失败返回False
        """
        try:
            logger.info("开始执行回关任务...")
            
            # 获取今日可回关数量
            max_follow_back_per_day = self.config.get('operation', {}).get('fan_list_tasks', {}).get('max_follow_back_per_day', 200)
            today_follow_backs = self.db.get_today_follow_back_count()
            
            if today_follow_backs >= max_follow_back_per_day:
                logger.info(f"今日回关数量 ({today_follow_backs}) 已达上限 ({max_follow_back_per_day})")
                return True
            
            # 获取待回关用户
            users_to_follow_back = self.db.get_users_to_follow_back(max_follow_back_per_day - today_follow_backs)
            
            if not users_to_follow_back:
                logger.info("没有需要回关的用户")
                return True
                
            logger.info(f"找到 {len(users_to_follow_back)} 个需要回关的用户")
            
            # 获取关注间隔时间
            follow_interval = self.config.get('operation', {}).get('fan_list_tasks', {}).get('follow_interval', [30, 60])
            min_interval, max_interval = follow_interval
            
            success_count = 0
            total_count = len(users_to_follow_back)
            current_count = 0
            
            for user in users_to_follow_back:
                current_count += 1
                try:
                    user_id = user['user_id']
                    username = user['username']
                    
                    logger.info(f"[{current_count}/{total_count}] 准备回关用户: {username} ({user_id})")
                    
                    # 访问用户主页
                    if not self.user_profile_manager.visit_user_profile(user_id):
                        logger.error(f"[{current_count}/{total_count}] 访问用户主页失败: {username} ({user_id})")
                        continue
                    
                    # 执行关注操作
                    if self.follow_user(user_id, username):
                        success_count += 1
                        # 更新数据库
                        self.db.update_fan_follow_back(user_id)
                        logger.info(f"[{current_count}/{total_count}] 成功回关用户: {username} ({user_id})")
                    else:
                        logger.error(f"[{current_count}/{total_count}] 回关用户失败: {username} ({user_id})")
                    
                    # 随机等待一段时间
                    wait_time = random.uniform(min_interval, max_interval)
                    if current_count < total_count:  # 如果不是最后一个用户
                        logger.info(f"[{current_count}/{total_count}] 等待 {wait_time:.2f} 秒后处理下一个用户")
                        time.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"[{current_count}/{total_count}] 处理回关用户时出错: {str(e)}")
                    continue
            
            logger.info(f"回关任务完成，成功回关 {success_count}/{total_count} 个用户")
            return True
            
        except Exception as e:
            logger.error(f"执行回关任务失败: {str(e)}")
            return False

    def follow_user(self, user_id, username):
        """对单个用户执行回关操作"""
        try:
            # 访问用户主页
            logger.info(f"访问用户 {username} ({user_id}) 的主页")
            self.driver.get(f"https://www.douyin.com/user/{user_id}")
            self.random_sleep(3, 5)
            
            # 查找并点击关注按钮
            follow_button = self.find_follow_button()
            if not follow_button:
                return False
            
            # 点击关注按钮
            if not self.click_follow_button(follow_button):
                return False
            
            # 确认关注成功
            if self.confirm_follow_success():
                self.db.mark_user_followed_back(user_id)
                logger.info(f"成功回关用户 {username}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"回关用户失败: {str(e)}")
            return False

    def find_follow_button(self):
        """查找关注按钮"""
        button_selectors = [
            "//button[@data-e2e='user-info-follow-btn'][contains(@class, 'semi-button-primary')]//span[contains(text(), '回关')]/..",
            "//button[@data-e2e='user-info-follow-btn'][contains(@class, 'semi-button-primary')]",
            "//button[contains(., '关注')]",
            "//button[contains(@class, 'follow-button') and contains(., '关注')]"
        ]
        
        for selector in button_selectors:
            try:
                buttons = self.driver.find_elements(By.XPATH, selector)
                for button in buttons:
                    button_text = button.text.strip()
                    if ('回关' in button_text or '关注' in button_text) and \
                       '已关注' not in button_text and \
                       '互相关注' not in button_text and \
                       '相互关注' not in button_text:
                        return button
            except:
                continue
        return None

    def click_follow_button(self, button):
        """点击关注按钮"""
        try:
            button.click()
            self.random_sleep(1, 2)
            return True
        except:
            try:
                self.driver.execute_script("arguments[0].click();", button)
                self.random_sleep(1, 2)
                return True
            except Exception as e:
                logger.error(f"点击关注按钮失败: {str(e)}")
                return False

    def confirm_follow_success(self):
        """确认关注是否成功"""
        try:
            mutual_button = self.wait.until(
                lambda d: d.find_element(By.XPATH, "//button[@data-e2e='user-info-follow-btn'][contains(@class, 'semi-button-secondary')]//span[contains(text(), '相互关注')]/..")
            )
            return bool(mutual_button)
        except Exception as e:
            logger.warning(f"未能确认关注状态: {str(e)}")
            return False

    def start_fan_interaction(self, user_id, username):
        """
        启动与新粉丝的互动流程
        
        参数:
            user_id: 粉丝ID
            username: 粉丝用户名
            
        返回:
            bool: 互动是否成功启动
        """
        try:
            logger.info(f"开始与新粉丝 {username} ({user_id}) 的互动流程")
            
            # 检查今日私信数量是否已达上限
            if self.db.get_today_message_count() >= self.config.get('operation', {}).get('fan_list_tasks', {}).get('max_messages_per_day', 100):
                logger.info("今日私信数量已达上限，跳过私信任务")
                return False
            
            # 发送第一天的欢迎消息
            if self.send_welcome_message(user_id, username):
                logger.info(f"成功启动与粉丝 {username} 的互动流程")
                return True
            else:
                logger.warning(f"启动与粉丝 {username} 的互动流程失败")
                return False
            
        except Exception as e:
            logger.error(f"启动粉丝互动流程失败: {str(e)}")
            return False

    def send_welcome_message(self, user_id, username):
        """发送欢迎消息给新粉丝"""
        try:
            # 检查今日私信数量是否已达上限
            if self.db.get_today_message_count() >= self.config.get('operation', {}).get('fan_list_tasks', {}).get('max_messages_per_day', 100):
                logger.info("今日私信数量已达上限，跳过私信任务")
                return False
            
            # 发送第一天的私信（days_since_follow = 0）
            if self.message_manager.send_message(user_id, username, 0):
                # 更新粉丝互动状态
                self.db.update_fan_interaction(user_id)
                logger.info(f"已成功发送欢迎消息给新粉丝 {username}")
                return True
            else:
                logger.warning(f"发送欢迎消息给新粉丝 {username} 失败")
                return False
            
        except Exception as e:
            logger.error(f"发送欢迎消息失败: {str(e)}")
            return False

    def run_fan_interaction_task(self):
        """
        执行粉丝互动任务
        
        功能：
        1. 检查所有需要互动的粉丝
        2. 根据关注天数发送不同的互动消息
        3. 更新互动状态
        """
        try:
            logger.info("开始执行粉丝互动任务...")
            
            # 获取今日可发送私信数量
            max_messages_per_day = self.config.get('operation', {}).get('fan_list_tasks', {}).get('max_messages_per_day', 100)
            today_messages = self.db.get_today_message_count()
            
            if today_messages >= max_messages_per_day:
                logger.info(f"今日私信数量 ({today_messages}) 已达上限 ({max_messages_per_day})")
                return True
            else:
                logger.info(f"今日已经对 ({today_messages}) 个粉丝发送私信")
            # 获取需要互动的粉丝
            remaining_messages = max_messages_per_day - today_messages
            fans_need_message = self.db.get_fans_need_message(limit=remaining_messages)
            
            if not fans_need_message:
                logger.info("没有需要互动的粉丝")
                return True
            
            logger.info(f"找到 {len(fans_need_message)} 个需要互动的粉丝")
            
            # 处理每个需要互动的粉丝
            success_count = 0
            total_count = len(fans_need_message)  # 总待处理数量
            current_count = 0  # 当前处理的粉丝序号
            
            for fan in fans_need_message:
                current_count += 1
                try:
                    # 检查必要的字段是否存在
                    if not all(key in fan for key in ['user_id', 'username', 'days_since_follow']):
                        logger.warning(f"[{current_count}/{total_count}] 粉丝数据缺少必要字段: {fan}")
                        continue
                        
                    user_id = fan['user_id']
                    username = fan['username']
                    days_since_follow = fan['days_since_follow']
                    
                    # 验证days_since_follow的值是否有效
                    if not isinstance(days_since_follow, int) or days_since_follow not in [0, 1, 2]:
                        logger.warning(f"[{current_count}/{total_count}] 粉丝 {username} 的days_since_follow值无效: {days_since_follow}")
                        continue
                    
                    logger.info(f"[{current_count}/{total_count}] 正在处理粉丝: {username} ({user_id}), 关注天数: {days_since_follow + 1}")
                    
                    # 发送对应天数的互动消息
                    if self.message_manager.send_message(user_id, username, days_since_follow):
                        success_count += 1
                        # 更新粉丝互动状态
                        self.db.update_fan_interaction(user_id)
                        logger.info(f"[{current_count}/{total_count}] 完成与粉丝 {username} 的第 {days_since_follow + 1} 天互动")
                    else:
                        logger.warning(f"[{current_count}/{total_count}] 与粉丝 {username} 的第 {days_since_follow + 1} 天互动失败")
                    
                except Exception as e:
                    logger.error(f"[{current_count}/{total_count}] 处理粉丝 {fan.get('username', 'unknown')} 的互动任务失败: {str(e)}")
                    continue
            
            logger.info(f"粉丝互动任务执行完成，成功发送 {success_count}/{total_count} 条私信")
            return True
            
        except Exception as e:
            logger.error(f"执行粉丝互动任务失败: {str(e)}")
            return False