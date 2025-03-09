"""
任务运行模块

该模块提供了任务调度和执行的功能。
"""

import time
import random
from datetime import datetime
from .logger import logger, save_screenshot, save_html
from selenium.webdriver.common.by import By

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
        
    def run_tasks(self):
        """
        运行任务
        
        返回:
            成功返回True，失败返回False
        """
        try:
            # 检查浏览器是否已关闭
            if self.browser_manager.is_browser_closed():
                logger.error("浏览器已关闭，无法执行任务")
                return False
                
            # 检查当前时间是否在工作时间范围内
            current_hour = datetime.now().hour
            
            # 检查是否启用全天运行模式
            all_day_operation = self.config.get('all_day_operation', False)
            
            # 如果不是全天运行模式且不是测试模式，检查工作时间
            if not all_day_operation and not self.config.get('test_mode', False):
                start_hour = self.config.get('working_hours', {}).get('start', 9)
                end_hour = self.config.get('working_hours', {}).get('end', 22)
                
                if current_hour < start_hour or current_hour >= end_hour:
                    logger.info(f"当前时间 {current_hour} 不在工作时间范围内 ({start_hour}-{end_hour})")
                    return False
            else:
                if all_day_operation:
                    logger.info("全天运行模式已启用，忽略工作时间限制")
                elif self.config.get('test_mode', False):
                    logger.info("测试模式已启用，忽略工作时间限制")
            
            # 获取今日关注和取关数量
            try:
                self.today_follows = self.db.get_today_follow_count()
                self.today_unfollows = self.db.get_today_unfollow_count()
                logger.info(f"今日已关注: {self.today_follows}, 已取关: {self.today_unfollows}")
            except Exception as e:
                logger.error(f"获取今日关注和取关数量失败: {str(e)}")
                self.today_follows = 0
                self.today_unfollows = 0
                logger.info("使用默认值: 今日已关注: 0, 已取关: 0")
            
            # 获取功能开关配置
            features = self.config.get('features', {})
            follow_fans_enabled = features.get('follow_fans', True)
            check_follows_enabled = features.get('check_follows', True)
            unfollow_users_enabled = features.get('unfollow_users', True)
            
            logger.info(f"功能开关状态: 关注粉丝({follow_fans_enabled}), 审查关注列表({check_follows_enabled}), 取关用户({unfollow_users_enabled})")
            
            # 1. 执行取关功能
            if unfollow_users_enabled:
                self.run_unfollow_task()
            else:
                logger.info("取关功能已禁用，跳过取关任务")
                
            # 2. 执行关注粉丝功能
            if follow_fans_enabled:
                self.run_follow_fans_task()
            else:
                logger.info("关注粉丝功能已禁用，跳过关注粉丝任务")
                
            # 3. 执行审查关注列表功能
            if check_follows_enabled:
                self.run_check_follows_task()
            else:
                logger.info("审查关注列表功能已禁用，跳过审查关注列表任务")
            
            logger.info(f"任务执行完成，今日已关注: {self.today_follows}, 已取关: {self.today_unfollows}")
            return True
            
        except Exception as e:
            logger.error(f"执行任务失败: {str(e)}")
            # 保存错误截图
            save_screenshot(self.driver, "error", level="ERROR")
            return False
            
    def run_unfollow_task(self):
        """执行取关任务"""
        logger.info("开始执行取关任务...")
        try:
            if self.today_unfollows < self.config.get('operation', {}).get('daily_unfollow_limit', 100):
                try:
                    # 获取需要取关的用户
                    unfollow_days = self.config.get('operation', {}).get('unfollow_days', 3)
                    unfollow_limit = self.config.get('operation', {}).get('daily_unfollow_limit', 100) - self.today_unfollows
                    
                    users_to_unfollow = self.db.get_users_to_unfollow(unfollow_days, unfollow_limit)
                    
                    if users_to_unfollow:
                        logger.info(f"找到 {len(users_to_unfollow)} 个需要取关的用户")
                        
                        for user in users_to_unfollow:
                            # 检查是否达到每日取关上限
                            if self.today_unfollows >= self.config.get('operation', {}).get('daily_unfollow_limit', 100):
                                logger.info(f"已达到每日取关上限: {self.config.get('operation', {}).get('daily_unfollow_limit', 100)}")
                                break
                                
                            # 访问用户主页
                            success = self.user_profile_manager.visit_user_profile(user['username'])
                            
                            if not success:
                                logger.warning(f"访问用户主页失败: {user['username']}，跳过取关")
                                continue
                                
                            # 执行取关操作
                            success = self.follow_manager.unfollow_user(user['username'], user['user_id'])
                            
                            if success:
                                self.today_unfollows += 1
                                logger.info(f"成功取关用户: {user['username']}, 今日已取关: {self.today_unfollows}")
                            else:
                                logger.warning(f"取关用户失败: {user['username']}")
                                
                            # 随机等待
                            unfollow_interval = self.config.get('operation', {}).get('unfollow_interval', [20, 40])
                            wait_time = random.uniform(unfollow_interval[0], unfollow_interval[1])
                            logger.info(f"等待 {wait_time:.2f} 秒后继续")
                            time.sleep(wait_time)
                    else:
                        logger.info("没有找到需要取关的用户")
                        
                except Exception as e:
                    logger.error(f"处理取关任务失败: {str(e)}")
                    # 保存错误截图
                    save_screenshot(self.driver, "unfollow_error", level="ERROR")
            else:
                logger.info(f"已达到每日取关上限: {self.config.get('operation', {}).get('daily_unfollow_limit', 100)}")
        except Exception as e:
            logger.error(f"取关任务整体执行失败: {str(e)}")
            save_screenshot(self.driver, "unfollow_task_error", level="ERROR")
            
    def run_follow_fans_task(self):
        """执行关注粉丝任务"""
        logger.info("开始执行关注粉丝任务...")
        try:
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
                        # 继续处理，假设未处理过
                        
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
            else:
                logger.info(f"已达到每日关注上限: {self.config.get('operation', {}).get('daily_follow_limit', 150)}")
        except Exception as e:
            logger.error(f"关注粉丝任务整体执行失败: {str(e)}")
            save_screenshot(self.driver, "follow_task_error", level="ERROR")
            
    def run_check_follows_task(self):
        """执行审查关注列表任务"""
        logger.info("开始执行审查关注列表任务...")
        try:
            # 访问个人主页
            logger.info("访问个人主页...")
            self.driver.get("https://www.douyin.com/user")
            self.random_sleep(3, 5)
            
            # 保存个人主页截图
            save_screenshot(self.driver, "check_follows_profile", level="NORMAL")
            
            # 点击关注标签 - 使用更多的选择器组合来增加匹配成功率
            logger.info("尝试点击关注标签...")
            follow_tab_found = False
            
            # 尝试多种可能的选择器
            selectors = [
                "//div[contains(@class, 'tab-item') and contains(text(), '关注')]",
                "//div[contains(text(), '关注') and contains(@class, 'tab')]",
                "//span[contains(text(), '关注') and ancestor::div[contains(@class, 'tab')]]",
                "//a[contains(@href, 'following') or contains(@href, 'follow')]",
                "//div[contains(@data-e2e, 'following-tab') or contains(@data-e2e, 'follow-tab')]",
                "//div[contains(text(), '关注') and not(contains(text(), '粉丝'))]"
            ]
            
            # 尝试每一个选择器
            for selector in selectors:
                try:
                    follow_tabs = self.driver.find_elements(By.XPATH, selector)
                    if follow_tabs:
                        logger.info(f"找到关注标签，使用选择器: {selector}")
                        follow_tabs[0].click()
                        follow_tab_found = True
                        self.random_sleep(3, 5)
                        break
                except Exception as e:
                    logger.warning(f"使用选择器 {selector} 查找关注标签失败: {str(e)}")
            
            # 如果所有选择器都失败，尝试使用JavaScript点击
            if not follow_tab_found:
                logger.info("尝试使用JavaScript点击关注标签...")
                try:
                    # 尝试通过文本内容查找并点击
                    self.driver.execute_script("""
                        var elements = document.querySelectorAll('div, span, a');
                        for (var i = 0; i < elements.length; i++) {
                            if (elements[i].textContent.includes('关注') && !elements[i].textContent.includes('粉丝')) {
                                elements[i].click();
                                return true;
                            }
                        }
                        return false;
                    """)
                    follow_tab_found = True
                    self.random_sleep(3, 5)
                except Exception as e:
                    logger.warning(f"使用JavaScript点击关注标签失败: {str(e)}")
            
            # 如果仍然无法找到关注标签，尝试直接访问关注页面
            if not follow_tab_found:
                logger.info("尝试直接访问关注页面...")
                try:
                    # 尝试直接访问关注页面
                    self.driver.get("https://www.douyin.com/user/following")
                    follow_tab_found = True
                    self.random_sleep(3, 5)
                except Exception as e:
                    logger.warning(f"直接访问关注页面失败: {str(e)}")
            
            # 如果所有方法都失败，则报错并退出
            if not follow_tab_found:
                logger.warning("未找到关注标签，无法查看关注列表")
                save_screenshot(self.driver, "check_follows_no_tab", level="ERROR")
                return False
                
            # 保存关注列表页面截图
            save_screenshot(self.driver, "check_follows_list", level="NORMAL")
            save_html(self.driver, "check_follows_list", level="NORMAL")
            
            # 获取关注列表
            logger.info("获取关注列表...")
            follow_items = []
            
            # 滚动加载更多关注
            max_scroll_times = 5  # 最多滚动5次
            for i in range(max_scroll_times):
                # 获取当前页面的关注项 - 使用多种选择器
                items = []
                selectors = [
                    "//div[contains(@class, 'follow-item') or contains(@class, 'user-item')]",
                    "//div[contains(@class, 'user-card') or contains(@class, 'user-box')]",
                    "//div[contains(@data-e2e, 'user-item') or contains(@data-e2e, 'follow-item')]",
                    "//div[contains(@class, 'card') and .//a[contains(@href, '/user/')]]"
                ]
                
                for selector in selectors:
                    try:
                        found_items = self.driver.find_elements(By.XPATH, selector)
                        if found_items:
                            items = found_items
                            logger.info(f"找到 {len(items)} 个关注项，使用选择器: {selector}")
                            break
                    except Exception as e:
                        logger.warning(f"使用选择器 {selector} 查找关注项失败: {str(e)}")
                
                current_count = len(follow_items)
                
                for item in items:
                    try:
                        # 提取用户信息 - 使用多种选择器
                        username = ""
                        username_selectors = [
                            ".//span[contains(@class, 'user-name') or contains(@class, 'nickname')]",
                            ".//span[contains(@class, 'name') or contains(@class, 'title')]",
                            ".//div[contains(@class, 'name') or contains(@class, 'title')]",
                            ".//a[contains(@href, '/user/')]"
                        ]
                        
                        for selector in username_selectors:
                            try:
                                username_elems = item.find_elements(By.XPATH, selector)
                                if username_elems:
                                    username = username_elems[0].text.strip()
                                    if username:
                                        break
                            except:
                                continue
                        
                        if not username:
                            continue
                        
                        # 检查是否已经添加过
                        if not any(f.get('username') == username for f in follow_items):
                            # 检查是否有互相关注标识
                            is_mutual = False
                            mutual_selectors = [
                                ".//span[contains(text(), '互相关注') or contains(text(), '互粉')]",
                                ".//div[contains(text(), '互相关注') or contains(text(), '互粉')]",
                                ".//span[contains(@class, 'mutual') or contains(@class, 'friend')]",
                                ".//div[contains(@class, 'mutual') or contains(@class, 'friend')]"
                            ]
                            
                            for selector in mutual_selectors:
                                try:
                                    mutual_elems = item.find_elements(By.XPATH, selector)
                                    if mutual_elems:
                                        is_mutual = True
                                        break
                                except:
                                    continue
                            
                            # 获取用户ID（从链接中提取）
                            user_id = ""
                            link_selectors = [
                                ".//a[contains(@href, '/user/')]",
                                ".//a[contains(@href, 'douyin.com/user/')]"
                            ]
                            
                            for selector in link_selectors:
                                try:
                                    link_elems = item.find_elements(By.XPATH, selector)
                                    if link_elems:
                                        href = link_elems[0].get_attribute('href')
                                        if href:
                                            user_id = href.split('/user/')[-1].split('?')[0]
                                            break
                                except:
                                    continue
                            
                            # 添加到列表
                            follow_items.append({
                                'username': username,
                                'user_id': user_id,
                                'is_mutual': is_mutual,
                                'element': item
                            })
                    except Exception as e:
                        logger.warning(f"提取关注用户信息失败: {str(e)}")
                
                # 如果没有新增关注项，停止滚动
                if len(follow_items) == current_count:
                    logger.info(f"滚动后未发现新的关注项，停止滚动")
                    break
                    
                # 滚动到页面底部加载更多
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                logger.info(f"滚动加载更多关注 ({i+1}/{max_scroll_times})...")
                self.random_sleep(2, 3)
            
            # 统计关注情况
            total_follows = len(follow_items)
            mutual_follows = sum(1 for item in follow_items if item['is_mutual'])
            non_mutual_follows = total_follows - mutual_follows
            
            logger.info(f"关注列表统计: 总关注 {total_follows}, 互相关注 {mutual_follows}, 未回关 {non_mutual_follows}")
            
            # 找出未回关的用户
            non_mutual_users = [item for item in follow_items if not item['is_mutual']]
            
            if non_mutual_users:
                logger.info(f"找到 {len(non_mutual_users)} 个未回关用户")
                
                # 将未回关用户信息保存到数据库，标记为待取关
                for user in non_mutual_users:
                    if user['user_id']:
                        try:
                            # 检查关注时间，如果超过指定天数则标记为待取关
                            unfollow_days = self.config.get('operation', {}).get('unfollow_days', 3)
                            self.db.mark_user_for_unfollow(user['user_id'], user['username'], unfollow_days)
                        except Exception as e:
                            logger.error(f"标记用户为待取关失败: {user['username']}, 错误: {str(e)}")
            else:
                logger.info("没有找到未回关用户")
                
            return True
            
        except Exception as e:
            logger.error(f"审查关注列表任务失败: {str(e)}")
            save_screenshot(self.driver, "check_follows_error", level="ERROR")
            return False