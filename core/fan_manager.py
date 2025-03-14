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
        
    def process_fan_item(self, fan_item):
        """
        处理单个粉丝项
        
        参数:
            fan_item: 粉丝项元素
            
        返回:
            dict: 包含粉丝信息的字典，如果处理失败则返回None
        """
        try:
            # 首先尝试获取用户ID，这是最关键的信息
            user_id = None
            try:
                link_element = fan_item.find_element(By.XPATH, ".//a[contains(@class, 'uz1VJwFY')]")
                href = link_element.get_attribute('href')
                if href and '/user/' in href:
                    user_id = href.split('/user/')[-1].split('?')[0]
            except:
                logger.warning("无法获取用户ID，跳过处理")
                return None
            
            if not user_id:
                logger.warning("未找到用户ID，跳过处理")
                return None
            
            # 尝试获取用户名，但即使获取失败也继续处理
            username = "未知用户"
            username_selectors = [
                ".//div[contains(@class, 'kUKK9Qal')]//span[contains(@class, 'arnSiSbK')]",
                ".//div[contains(@class, 'X8ljGzft')]//div[contains(@class, 'kUKK9Qal')]//span[contains(@class, 'arnSiSbK')]"
            ]
            
            for selector in username_selectors:
                try:
                    username_element = fan_item.find_element(By.XPATH, selector)
                    temp_username = username_element.text.strip()
                    if temp_username:
                        username = temp_username
                        break
                except:
                    continue
            
            # 检查关注状态和按钮
            ui_follow_status = None  # UI上显示的关注状态
            follow_button = None
            try:
                button = fan_item.find_element(By.XPATH, ".//button[contains(@class, 'xjIRvxqr')]")
                button_text = button.find_element(By.XPATH, ".//div[contains(@class, 'zPZJ3j40')]").text.strip()
                
                if "相互关注" in button_text:
                    ui_follow_status = "mutual"
                elif "回关" in button_text:
                    ui_follow_status = "need_follow_back"
                    follow_button = button
                elif "已请求" in button_text:
                    ui_follow_status = "requested"
                else:
                    ui_follow_status = "unknown"  # 未知状态
                
                logger.info(f"用户 {username} ({user_id}) 的UI关注状态: {ui_follow_status}, 按钮文本: {button_text}")
            except:
                logger.warning(f"无法获取用户 {username} ({user_id}) 的UI关注状态")
                ui_follow_status = "unknown"
            
            # 检查数据库中是否已存在该粉丝
            existing_fan = self.db.get_user_by_id(user_id)
            
            # 确定最终的关注状态
            if existing_fan:
                # 已存在的粉丝，使用数据库中的状态
                db_follow_status = existing_fan.get('follow_status', 'unknown')
                logger.info(f"用户 {username} ({user_id}) 在数据库中已存在，状态: {db_follow_status}")
                
                # 只有当UI状态与数据库状态不一致时才更新
                if ui_follow_status and ui_follow_status != "unknown" and ui_follow_status != db_follow_status:
                    logger.info(f"更新用户 {username} ({user_id}) 的关注状态: {db_follow_status} -> {ui_follow_status}")
                    self.db.add_fan_record(user_id, username, ui_follow_status)
                    follow_status = ui_follow_status
                else:
                    follow_status = db_follow_status
            else:
                # 新发现的粉丝
                if ui_follow_status and ui_follow_status != "unknown":
                    follow_status = ui_follow_status
                else:
                    # 默认为新粉丝
                    follow_status = "new_fan"
                logger.info(f"发现新粉丝: {username} ({user_id}), 状态: {follow_status}")
                
                # 将新粉丝信息保存到数据库
                self.db.add_fan_record(user_id, username, follow_status)
            
            return {
                'element': fan_item,
                'username': username,
                'user_id': user_id,
                'follow_status': follow_status,
                'follow_back_button': follow_button if follow_status == "need_follow_back" else None
            }
            
        except Exception as e:
            logger.error(f"处理粉丝项时出错: {str(e)}")
            return None

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
            processed_users = set()  # 使用集合存储已处理的用户ID
            result = []
            last_height = 0
            no_new_items_count = 0
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
                    
                    # 获取当前可见的粉丝项
                    fan_items = container.find_elements(By.XPATH, ".//div[contains(@class, 'i5U4dMnB')]")
                    current_count = len(fan_items)
                    
                    if current_count > 0:
                        logger.info(f"当前已加载 {current_count} 个粉丝项，已处理 {len(processed_users)} 个")
                    
                    # 处理新加载的粉丝项
                    for fan_item in fan_items:
                        try:
                            # 先尝试获取用户ID
                            user_id = None
                            try:
                                link_element = fan_item.find_element(By.XPATH, ".//a[contains(@class, 'uz1VJwFY')]")
                                href = link_element.get_attribute('href')
                                if href and '/user/' in href:
                                    user_id = href.split('/user/')[-1].split('?')[0]
                            except:
                                continue
                            
                            # 如果已经处理过该用户，跳过
                            if user_id in processed_users:
                                continue
                                
                            # 处理粉丝信息
                            fan_info = self.process_fan_item(fan_item)
                            if fan_info:
                                processed_users.add(user_id)  # 使用用户ID而不是用户名来标记
                                result.append(fan_info)
                                
                        except Exception as e:
                            logger.warning(f"处理粉丝项时出错: {str(e)}")
                            continue  # 继续处理下一个粉丝
                    
                    # 检查是否已加载所有粉丝
                    if len(processed_users) >= expected_total:
                        logger.info(f"已处理所有粉丝 ({len(processed_users)}/{expected_total})")
                        break
                    
                    # 滚动到底部并检查是否有新内容
                    try:
                        current_height = self.driver.execute_script("return arguments[0].scrollHeight", container)
                        if current_height == last_height:
                            no_new_items_count += 1
                            if no_new_items_count >= 5:
                                logger.info("连续5次滚动未发现新内容，停止滚动")
                                break
                        else:
                            no_new_items_count = 0
                            
                        self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
                        self.random_sleep(2, 3)
                        last_height = current_height
                    except Exception as e:
                        logger.warning(f"滚动操作失败: {str(e)}")
                        if retry_count < max_retries:
                            retry_count += 1
                            self.random_sleep(2, 3)
                            continue
                        else:
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
            total_element = self.driver.find_element(By.XPATH, "//div[@data-e2e='user-info-fans']//div[contains(@class, 'C1cxu0Vq')]")
            total_text = total_element.text.strip()
            expected_total = int(total_text.replace('万', '0000').replace('亿', '00000000'))
            logger.info(f"预期粉丝总数: {expected_total}")
            return expected_total
        except Exception as e:
            logger.warning(f"获取预期粉丝总数失败: {str(e)}")
            return None

    def calculate_scroll_attempts(self, expected_total):
        """计算需要滚动的次数"""
        if expected_total:
            return min(20, (expected_total // 15) + 2)
        return 10  # 默认滚动次数

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
            
            for user in users_to_follow_back:
                try:
                    user_id = user['user_id']
                    username = user['username']
                    
                    logger.info(f"准备回关用户: {username} ({user_id})")
                    
                    # 访问用户主页
                    if not self.user_profile_manager.visit_user_profile(user_id):
                        logger.error(f"访问用户主页失败: {username} ({user_id})")
                        continue
                    
                    # 执行关注操作
                    if self.follow_user(user_id, username):
                        success_count += 1
                        # 更新数据库
                        self.db.update_fan_follow_back(user_id)
                        logger.info(f"成功回关用户: {username} ({user_id})")
                    else:
                        logger.error(f"回关用户失败: {username} ({user_id})")
                    
                    # 随机等待一段时间
                    wait_time = random.uniform(min_interval, max_interval)
                    logger.info(f"等待 {wait_time:.2f} 秒后处理下一个用户")
                    time.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"处理回关用户时出错: {str(e)}")
                    continue
            
            logger.info(f"回关任务完成，成功回关 {success_count}/{len(users_to_follow_back)} 个用户")
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
            
            # 获取需要互动的粉丝
            remaining_messages = max_messages_per_day - today_messages
            fans_need_message = self.db.get_fans_need_message(limit=remaining_messages)
            
            if not fans_need_message:
                logger.info("没有需要互动的粉丝")
                return True
            
            logger.info(f"找到 {len(fans_need_message)} 个需要互动的粉丝")
            
            # 处理每个需要互动的粉丝
            success_count = 0
            for fan in fans_need_message:
                try:
                    # 检查必要的字段是否存在
                    if not all(key in fan for key in ['user_id', 'username', 'days_since_follow']):
                        logger.warning(f"粉丝数据缺少必要字段: {fan}")
                        continue
                        
                    user_id = fan['user_id']
                    username = fan['username']
                    days_since_follow = fan['days_since_follow']
                    
                    # 验证days_since_follow的值是否有效
                    if not isinstance(days_since_follow, int) or days_since_follow not in [0, 1, 2]:
                        logger.warning(f"粉丝 {username} 的days_since_follow值无效: {days_since_follow}")
                        continue
                    
                    # 发送对应天数的互动消息
                    if self.message_manager.send_message(user_id, username, days_since_follow):
                        success_count += 1
                        # 更新粉丝互动状态
                        self.db.update_fan_interaction(user_id)
                        logger.info(f"完成与粉丝 {username} 的第 {days_since_follow + 1} 天互动")
                    
                    # 随机延迟，避免操作过快
                    self.random_sleep(2, 5)
                    
                except Exception as e:
                    logger.error(f"处理粉丝 {fan.get('username', 'unknown')} 的互动任务失败: {str(e)}")
                    continue
            
            logger.info(f"粉丝互动任务执行完成，成功发送 {success_count}/{len(fans_need_message)} 条私信")
            return True
            
        except Exception as e:
            logger.error(f"执行粉丝互动任务失败: {str(e)}")
            return False