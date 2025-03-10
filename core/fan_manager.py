"""
粉丝管理模块

该模块提供了获取和处理粉丝列表的功能。
"""

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
from .logger import logger, save_screenshot, save_html, get_log_path
import json
import re
from datetime import datetime

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
            
            # 保存页面截图和源码，用于分析
            save_screenshot(self.driver, "fans_page", level="NORMAL")
            save_html(self.driver, "fans_page")
            
            # 查找粉丝列表容器
            container_selectors = [
                "//div[@data-e2e='user-fans-container']",
                "//div[contains(@class, 'FjupSA6k')]"
            ]
            
            container = None
            for selector in container_selectors:
                try:
                    containers = self.driver.find_elements(By.XPATH, selector)
                    if containers:
                        container = containers[0]
                        logger.info(f"找到粉丝列表容器: {selector}")
                        break
                except Exception as e:
                    logger.warning(f"使用选择器 {selector} 查找容器失败: {str(e)}")
            
            if not container:
                logger.error("未找到粉丝列表容器")
                return []
            
            # 获取预期的粉丝总数
            try:
                total_element = self.driver.find_element(By.XPATH, "//div[@data-e2e='user-info-fans']//div[contains(@class, 'C1cxu0Vq')]")
                total_text = total_element.text.strip()
                expected_total = int(total_text.replace('万', '0000').replace('亿', '00000000'))
                logger.info(f"预期粉丝总数: {expected_total}")
            except Exception as e:
                logger.warning(f"获取预期粉丝总数失败: {str(e)}")
                expected_total = None
            
            # 根据粉丝数量设置滚动次数
            if expected_total:
                # 假设每次滚动加载15个粉丝，额外增加2次滚动以确保加载完整
                max_scroll_attempts = min(20, (expected_total // 15) + 2)
            else:
                max_scroll_attempts = 10  # 如果无法获取总数，使用默认值
                
            logger.info(f"设置最大滚动次数: {max_scroll_attempts}")
            
            # 滚动加载粉丝
            last_height = 0
            no_new_items_count = 0
            processed_users = set()
            result = []
            
            for scroll_attempt in range(max_scroll_attempts):
                # 获取当前可见的粉丝项
                fan_items = container.find_elements(By.XPATH, ".//div[contains(@class, 'i5U4dMnB')]")
                current_count = len(fan_items)
                
                # 只在数量变化时才打印日志
                if len(result) != current_count:
                    logger.info(f"当前已加载 {current_count} 个粉丝项")
                
                # 如果已达到预期总数，可以提前结束
                if expected_total and current_count >= expected_total:
                    logger.info(f"已加载完所有粉丝 ({current_count}/{expected_total})")
                    break
                
                # 处理新加载的粉丝项
                for fan_item in fan_items:
                    try:
                        # 提取用户名
                        username = None
                        username_selectors = [
                            ".//div[contains(@class, 'kUKK9Qal')]//span[contains(@class, 'arnSiSbK')]",
                            ".//div[contains(@class, 'X8ljGzft')]//div[contains(@class, 'kUKK9Qal')]//span[contains(@class, 'arnSiSbK')]"
                        ]
                        
                        for selector in username_selectors:
                            try:
                                username_element = fan_item.find_element(By.XPATH, selector)
                                username = username_element.text.strip()
                                if username:
                                    break
                            except:
                                continue
                        
                        if not username:
                            continue
                            
                        # 检查是否已处理过该用户
                        if username in processed_users:
                            continue
                            
                        processed_users.add(username)
                        
                        # 提取用户ID
                        user_id = None
                        try:
                            link_element = fan_item.find_element(By.XPATH, ".//a[contains(@class, 'uz1VJwFY')]")
                            href = link_element.get_attribute('href')
                            if href and '/user/' in href:
                                user_id = href.split('/user/')[-1].split('?')[0]
                        except:
                            logger.warning(f"无法获取用户 {username} 的ID")
                            continue
                        
                        # 检查关注状态和按钮
                        follow_status = None
                        follow_button = None
                        try:
                            button = fan_item.find_element(By.XPATH, ".//button[contains(@class, 'xjIRvxqr')]")
                            button_text = button.find_element(By.XPATH, ".//div[contains(@class, 'zPZJ3j40')]").text.strip()
                            
                            if "相互关注" in button_text:
                                follow_status = "mutual"
                            elif "回关" in button_text:
                                follow_status = "need_follow_back"
                                follow_button = button
                            elif "已请求" in button_text:
                                follow_status = "requested"
                            
                            logger.info(f"用户 {username} 的关注状态: {follow_status}, 按钮文本: {button_text}")
                        except:
                            logger.warning(f"无法获取用户 {username} 的关注状态")
                            continue
                        
                        # 添加到结果列表
                        result.append({
                            'element': fan_item,
                            'username': username,
                            'user_id': user_id,
                            'follow_status': follow_status,
                            'follow_back_button': follow_button if follow_status == "need_follow_back" else None
                        })
                        
                    except Exception as e:
                        logger.warning(f"处理粉丝项时出错: {str(e)}")
                        continue
                
                # 检查是否需要继续滚动
                current_height = self.driver.execute_script("return arguments[0].scrollHeight", container)
                if current_height == last_height:
                    no_new_items_count += 1
                    if no_new_items_count >= 5:  # 增加到5次连续未加载新内容才停止
                        logger.info("连续5次滚动未发现新内容，停止滚动")
                        break
                else:
                    no_new_items_count = 0
                
                # 滚动到底部并增加等待时间
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
                self.random_sleep(2, 3)  # 增加等待时间，给页面更多加载时间
                last_height = current_height
            
            # 最终检查
            if expected_total and len(result) < expected_total:
                logger.warning(f"未能加载所有粉丝，实际加载 {len(result)} 个，预期 {expected_total} 个")
                # 尝试最后一次强制滚动
                if no_new_items_count >= 5:
                    logger.info("尝试最后一次强制滚动...")
                    self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
                    self.random_sleep(3, 5)
                    fan_items = container.find_elements(By.XPATH, ".//div[contains(@class, 'i5U4dMnB')]")
                    if len(fan_items) > len(result):
                        logger.info(f"强制滚动后新增了 {len(fan_items) - len(result)} 个粉丝项")
                        # 处理新增的粉丝项...
            
            logger.info(f"成功获取 {len(result)} 个粉丝信息")
            return result
            
        except Exception as e:
            logger.error(f"获取粉丝列表项失败: {str(e)}")
            return []
    
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
            
            # 获取配置参数
            max_fans_per_check = self.config.get('operation', {}).get('max_fans_per_check', 100)
            
            # 访问个人主页
            logger.info("访问个人主页...")
            self.driver.get("https://www.douyin.com/user/self")
            self.random_sleep(3, 5)
            
            # 点击粉丝标签并获取粉丝数量
            logger.info("点击粉丝标签...")
            success, total_fans_count = self.user_profile_manager.click_fans_tab()
            self.random_sleep(3, 5)
            
            if not success:
                logger.error("点击粉丝标签失败")
                return False
                
            logger.info(f"粉丝总数: {total_fans_count}")
            
            # 获取粉丝列表
            fan_items = self.get_fan_items()
            
            if not fan_items:
                logger.warning("未找到任何粉丝项")
                return False
            
            # 统计粉丝状态
            total_fans = len(fan_items)
            mutual_follows = sum(1 for item in fan_items if item['follow_status'] == "mutual")
            need_follow_back = sum(1 for item in fan_items if item['follow_status'] == "need_follow_back")
            requested = sum(1 for item in fan_items if item['follow_status'] == "requested")
            
            logger.info(f"粉丝统计: 总数={total_fans}, 互关={mutual_follows}, 待回关={need_follow_back}, 已请求={requested}")
            
            # 处理需要回关的用户
            if need_follow_back > 0:
                logger.info(f"找到 {need_follow_back} 个需要回关的用户")
                
                # 将需要回关的用户信息保存到数据库
                marked_count = 0
                
                # 批量处理待回关用户
                batch_size = 10
                need_follow_back_users = [item for item in fan_items if item['follow_status'] == "need_follow_back"]
                
                for i in range(0, len(need_follow_back_users), batch_size):
                    batch = need_follow_back_users[i:i+batch_size]
                    
                    for user in batch:
                        try:
                            if user['user_id']:  # 确保有用户ID
                                if self.db.mark_user_for_follow_back(user['user_id'], user['username']):
                                    marked_count += 1
                                    logger.info(f"已标记用户 {user['username']} ({user['user_id']}) 为待回关")
                        except Exception as e:
                            logger.error(f"标记用户为待回关失败: {user['username']}, 错误: {str(e)}")
                    
                    # 每批次处理后休息一下
                    if i + batch_size < len(need_follow_back_users):
                        time.sleep(0.5)
                
                logger.info(f"已标记 {marked_count} 个用户为待回关")
            else:
                logger.info("没有找到需要回关的用户")
            
            # 返回个人主页
            self.driver.get("https://www.douyin.com/user/self")
            self.random_sleep(2, 3)
            
            return True
        except Exception as e:
            logger.error(f"检查粉丝列表任务失败: {str(e)}")
            save_screenshot(self.driver, "fans_check_error")
            return False
    
    def run_follow_back_task(self):
        """
        执行回关任务
        
        功能：对已标记为待回关的用户进行回关操作。
        
        参数说明：
        - max_follow_back_per_day：配置文件中设置的每日最大回关数量。
        - follow_back_interval：两次回关操作之间的最小时间间隔（秒）。
        
        返回：
        - 成功返回True，失败返回False。
        - 返回的数据包括成功回关的用户数量。
        """
        try:
            logger.info("开始执行回关任务...")
            
            # 获取配置参数
            max_follow_back_per_day = self.config.get('operation', {}).get('max_follow_back_per_day', 200)
            follow_back_interval = self.config.get('operation', {}).get('follow_back_interval', 3)
            
            # 检查今日回关数量是否已达上限
            today_follow_backs = self.db.get_today_follow_back_count()
            
            if today_follow_backs >= max_follow_back_per_day:
                logger.info(f"今日回关数量 ({today_follow_backs}) 已达上限 ({max_follow_back_per_day})，跳过回关任务")
                return True
            
            # 获取待回关用户列表
            users_to_follow_back = self.db.get_users_to_follow_back(max_follow_back_per_day - today_follow_backs)
            
            if not users_to_follow_back:
                logger.info("没有待回关的用户，跳过回关任务")
                return True
            
            logger.info(f"找到 {len(users_to_follow_back)} 个待回关用户")
            
            # 执行回关操作
            success_count = 0
            
            for user in users_to_follow_back:
                user_id = user.get('user_id')
                username = user.get('username')
                
                if not user_id:
                    logger.warning(f"用户 {username} 缺少ID，跳过")
                    continue
                
                try:
                    # 访问用户主页
                    logger.info(f"访问用户 {username} ({user_id}) 的主页")
                    self.driver.get(f"https://www.douyin.com/user/{user_id}")
                    self.random_sleep(3, 5)
                    
                    # 查找关注按钮
                    follow_button = None
                    button_selectors = [
                        # 新版关注按钮选择器
                        "//button[@data-e2e='user-info-follow-btn'][contains(@class, 'semi-button-primary')]//span[contains(text(), '回关')]/..",
                        "//button[@data-e2e='user-info-follow-btn'][contains(@class, 'semi-button-primary')]",
                        # 旧版选择器作为备用
                        "//button[contains(., '关注')]",
                        "//button[contains(@class, 'follow-button') and contains(., '关注')]",
                        "//div[contains(@class, 'follow-button') and contains(., '关注')]",
                        "//button[@data-e2e='user-follow']"
                    ]
                    
                    for selector in button_selectors:
                        try:
                            buttons = self.driver.find_elements(By.XPATH, selector)
                            for button in buttons:
                                button_text = button.text.strip()
                                # 检查按钮文本和类名
                                if ('回关' in button_text or '关注' in button_text) and \
                                   '已关注' not in button_text and \
                                   '互相关注' not in button_text and \
                                   '相互关注' not in button_text:
                                    # 验证按钮是否可点击
                                    if 'semi-button-primary' in button.get_attribute('class'):
                                        follow_button = button
                                        logger.info(f"找到可用的关注按钮，选择器: {selector}, 文本: {button_text}")
                                        break
                            if follow_button:
                                break
                        except Exception as e:
                            logger.debug(f"使用选择器 {selector} 查找按钮失败: {str(e)}")
                            continue
                    
                    if not follow_button:
                        logger.warning(f"未找到用户 {username} 的关注按钮，可能已关注或页面结构变化")
                        # 检查是否已经互相关注
                        try:
                            mutual_button = self.driver.find_element(By.XPATH, "//button[@data-e2e='user-info-follow-btn'][contains(@class, 'semi-button-secondary')]//span[contains(text(), '相互关注')]/..")
                            if mutual_button:
                                logger.info(f"检测到与用户 {username} 已经互相关注")
                                # 只有确认是互相关注状态才更新数据库
                                self.db.mark_user_followed_back(user_id)
                        except:
                            logger.warning(f"用户 {username} 的关注按钮状态异常，跳过处理")
                        continue
                    
                    # 点击关注按钮
                    logger.info(f"点击关注按钮，关注用户 {username}")
                    follow_success = False
                    try:
                        # 先尝试常规点击
                        follow_button.click()
                        self.random_sleep(1, 2)
                        follow_success = True
                    except:
                        # 如果常规点击失败，尝试使用JavaScript点击
                        try:
                            self.driver.execute_script("arguments[0].click();", follow_button)
                            self.random_sleep(1, 2)
                            follow_success = True
                        except Exception as e:
                            logger.error(f"点击关注按钮失败: {str(e)}")
                            continue
                    
                    # 等待按钮状态变化
                    if follow_success:
                        try:
                            # 等待按钮变为"相互关注"状态
                            mutual_button = self.wait.until(
                                lambda d: d.find_element(By.XPATH, "//button[@data-e2e='user-info-follow-btn'][contains(@class, 'semi-button-secondary')]//span[contains(text(), '相互关注')]/..")
                            )
                            if mutual_button:
                                logger.info(f"确认关注状态已变更为相互关注")
                                # 只有在确认状态变更后才更新数据库
                                self.db.mark_user_followed_back(user_id)
                                success_count += 1
                                logger.info(f"成功关注用户 {username} ({user_id})，当前进度: {success_count}/{len(users_to_follow_back)}")
                            else:
                                logger.warning(f"未能确认用户 {username} 的关注状态变更为相互关注")
                        except Exception as e:
                            logger.warning(f"等待关注状态变更超时: {str(e)}")
                            save_screenshot(self.driver, f"follow_back_status_error_{user_id}")
                            continue
                    
                    # 保存截图
                    save_screenshot(self.driver, f"follow_back_{user_id}", level="NORMAL")
                    
                    # 等待指定时间间隔
                    self.random_sleep(follow_back_interval, follow_back_interval + 10)
                except Exception as e:
                    logger.error(f"回关用户 {username} ({user_id}) 失败: {str(e)}")
                    save_screenshot(self.driver, f"follow_back_error_{user_id}")
                    self.random_sleep(5, 10)
                    continue
            
            logger.info(f"回关任务完成，成功回关 {success_count} 个用户")
            
            # 返回个人主页
            self.driver.get("https://www.douyin.com/user/self")
            self.random_sleep(2, 3)
            
            return True
        except Exception as e:
            logger.error(f"回关任务失败: {str(e)}")
            save_screenshot(self.driver, "follow_back_error")
            return False