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
from .follow_manager import FollowListManager

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
        # 初始化关注列表管理器
        self.follow_list_manager = FollowListManager(browser_manager, db, config)
        
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
                
    def run_tasks(self):
        """
        运行任务
        
        返回:
            任务结果字典，包含任务类型和间隔时间等信息
        """
        try:
            # 检查浏览器状态
            logger.info("检查浏览器状态...")
            if not self.browser_manager.check_and_restart_browser():
                logger.error("浏览器状态异常，无法执行任务")
                return {'success': False, 'reason': '浏览器状态异常'}
            
            # 执行取关任务
            try:
                if self.run_unfollow_task():
                    logger.info("取关任务执行成功")
                else:
                    logger.warning("取关任务执行失败，检查浏览器状态")
                    if not self.browser_manager.check_and_restart_browser():
                        logger.error("浏览器状态异常，无法继续执行任务")
                        return {'success': False, 'reason': '浏览器状态异常'}
            except Exception as e:
                logger.error(f"执行取关任务时出错: {str(e)}")
                self.handle_task_failure("执行取关任务时出错", e)
            
            # 执行检查关注列表任务
            try:
                if self.follow_list_manager.run_check_follows_task():
                    # 获取配置的任务间隔时间
                    task_interval = self.config.get('task', {}).get('check_follows_interval', 3600)  # 默认1小时
                    logger.info(f"检查关注列表任务完成，休息 {task_interval} 秒后执行下一轮任务")
                    return {
                        'success': True,
                        'task_type': 'check_follows',
                        'interval': task_interval
                    }
                else:
                    logger.warning("检查关注列表任务执行失败，检查浏览器状态")
                    if not self.browser_manager.check_and_restart_browser():
                        logger.error("浏览器状态异常，无法继续执行任务")
                        return {'success': False, 'reason': '浏览器状态异常'}
            except Exception as e:
                logger.error(f"执行检查关注列表任务时出错: {str(e)}")
                self.handle_task_failure("执行检查关注列表任务时出错", e)
            
            # 执行关注粉丝任务
            try:
                if self.run_follow_fans_task():
                    logger.info("关注粉丝任务执行成功")
                else:
                    logger.warning("关注粉丝任务执行失败，检查浏览器状态")
                    if not self.browser_manager.check_and_restart_browser():
                        logger.error("浏览器状态异常，无法继续执行任务")
                        return {'success': False, 'reason': '浏览器状态异常'}
            except Exception as e:
                logger.error(f"执行关注粉丝任务时出错: {str(e)}")
                self.handle_task_failure("执行关注粉丝任务时出错", e)
            
            return {'success': True}
        except Exception as e:
            logger.error(f"执行任务时出错: {str(e)}")
            self.handle_task_failure("执行任务时出错", e)
            return {'success': False, 'reason': str(e)}
        
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
            unfollow_count_today = self.db.get_today_unfollow_count()
            remaining_unfollow = max_unfollow_per_day - unfollow_count_today
            
            logger.info(f"今日剩余可取关数量: {remaining_unfollow}")
            
            if remaining_unfollow <= 0:
                logger.info("今日取关数量已达上限，跳过取关任务")
                return True
            
            # 获取取关天数阈值
            unfollow_days = self.config.get('operation', {}).get('unfollow_days', 3)
            
            # 获取需要取关的用户
            users_to_unfollow = self.db.get_users_to_unfollow(remaining_unfollow, unfollow_days)
            
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
                        if self.follow_manager.unfollow_user(user['username'], user['user_id']):
                            success_count += 1
                            # 更新数据库中的用户状态
                            self.db.remove_follow_record(user['user_id'])
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
        """
        执行关注粉丝任务
        """
        # 检查今日关注数量是否已达上限
        max_follow_per_day = self.config.get('operation', {}).get('daily_follow_limit', 150)
        today_follows = self.db.get_today_follow_count()
        
        if today_follows < max_follow_per_day:
            logger.info(f"今日已关注: {today_follows}, 上限: {max_follow_per_day}")
            
            # 获取目标用户列表
            target_users = self.config.get('target_users', [])
            
            if not target_users:
                logger.warning("未配置目标用户，跳过关注粉丝任务")
                return False
            
            # 获取未处理的目标用户
            unprocessed_users = self.db.get_unprocessed_target_users(target_users)
            
            if not unprocessed_users:
                logger.info("所有目标用户今日已处理，跳过关注粉丝任务")
                return True
            
            # 随机选择一个目标用户
            target_user = random.choice(unprocessed_users)
            logger.info(f"选择目标用户: {target_user}")
            
            try:
                # 访问目标用户主页
                self.driver.get(f"https://www.douyin.com/user/{target_user}")
                self.random_sleep(3, 5)
                
                # 点击粉丝按钮
                try:
                    fans_button = self.driver.find_element(By.XPATH, "//div[contains(@class, 'count-item') and contains(., '粉丝')]")
                    fans_button.click()
                    self.random_sleep(2, 3)
                except Exception as e:
                    logger.error(f"点击粉丝按钮失败: {str(e)}")
                    self.handle_task_failure("点击粉丝按钮失败", e, "fans_button_error")
                    return False
                
                # 获取粉丝列表
                fans_items = []
                try:
                    # 使用更精确的选择器
                    fans_items = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'i5U4dMnB')]")
                    if not fans_items:
                        # 尝试备用选择器
                        fans_items = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'user-item')]")
                    
                    logger.info(f"找到 {len(fans_items)} 个粉丝")
                except Exception as e:
                    logger.error(f"获取粉丝列表失败: {str(e)}")
                    self.handle_task_failure("获取粉丝列表失败", e, "fans_list_error")
                    return False
                
                # 关注粉丝
                follow_count = 0
                max_follows = min(max_follow_per_day - today_follows, 20)  # 每次最多关注20个
                
                for i, fan_item in enumerate(fans_items):
                    if follow_count >= max_follows:
                        logger.info(f"已达到本次关注上限: {max_follows}")
                        break
                    
                    try:
                        # 提取粉丝信息
                        fan_info = {}
                        
                        # 提取用户名
                        try:
                            username_element = fan_item.find_element(By.XPATH, ".//p[contains(@class, 'kUKK9Qal')]")
                            fan_info['username'] = username_element.text.strip()
                        except:
                            try:
                                # 尝试备用选择器
                                username_element = fan_item.find_element(By.XPATH, ".//span[contains(@class, 'nickname')]")
                                fan_info['username'] = username_element.text.strip()
                            except:
                                logger.warning(f"无法获取第 {i+1} 个粉丝的用户名")
                                continue
                        
                        # 提取用户ID
                        try:
                            link_element = fan_item.find_element(By.XPATH, ".//a[contains(@href, '/user/')]")
                            href = link_element.get_attribute('href')
                            if href and '/user/' in href:
                                fan_info['user_id'] = href.split('/user/')[-1].split('?')[0]
                            else:
                                logger.warning(f"无法从链接提取用户ID: {href}")
                                continue
                        except:
                            logger.warning(f"无法获取第 {i+1} 个粉丝的用户ID")
                            continue
                        
                        # 检查是否已关注
                        if self.db.is_followed(fan_info['user_id']):
                            logger.info(f"已关注用户: {fan_info['username']} ({fan_info['user_id']}), 跳过")
                            continue
                        
                        # 关注用户
                        if self.follow_manager.follow_user(fan_info):
                            follow_count += 1
                            self.today_follows += 1
                            logger.info(f"成功关注用户: {fan_info['username']} ({fan_info['user_id']}), 当前进度: {follow_count}/{max_follows}")
                            self.random_sleep(5, 10)  # 关注后等待一段时间
                        else:
                            logger.warning(f"关注用户失败: {fan_info['username']} ({fan_info['user_id']})")
                            self.random_sleep(3, 5)
                    except Exception as e:
                        logger.error(f"处理粉丝项时出错: {str(e)}")
                        self.random_sleep(2, 4)
                        continue
                
                # 标记目标用户为已处理
                self.db.mark_target_user_processed(target_user, follow_count)
                logger.info(f"目标用户 {target_user} 已处理, 关注了 {follow_count} 个粉丝")
                
                # 返回个人主页
                try:
                    self.driver.get("https://www.douyin.com/user")
                    logger.info("通过URL返回个人主页: https://www.douyin.com/user/self")
                    self.random_sleep(2, 3)
                except Exception as e:
                    self.handle_task_failure("返回个人主页失败", e)
                    
            except Exception as e:
                logger.error(f"关注粉丝任务失败: {str(e)}")
                self.handle_task_failure("关注粉丝任务失败", e, "follow_fans_error")
                return False
                
            return True
        else:
            logger.info(f"已达到每日关注上限: {self.config.get('operation', {}).get('daily_follow_limit', 150)}")
            return True