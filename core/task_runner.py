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
from .follow_fans_manager import FollowFansManager
from .video_comment_manager import VideoCommentManager

class TaskRunner:
    """任务运行类，负责任务调度和执行"""
    
    def __init__(self, browser_manager, user_profile_manager, fan_manager, follow_manager, db, config, follow_fans_manager=None, video_comment_manager=None):
        """
        初始化任务运行器
        
        参数:
            browser_manager: 浏览器管理器对象
            user_profile_manager: 用户资料管理器对象
            fan_manager: 粉丝管理器对象
            follow_manager: 关注管理器对象
            db: 数据库对象
            config: 配置对象
            follow_fans_manager: 粉丝关注管理器对象，如果为None则创建新的
            video_comment_manager: 视频评论管理器对象，如果为None则创建新的
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
        # 初始化粉丝关注管理器
        self.follow_fans_manager = follow_fans_manager or FollowFansManager(browser_manager, db, config)
        # 初始化视频评论管理器
        self.video_comment_manager = video_comment_manager or VideoCommentManager(browser_manager, db, config)
        
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
            
            # 获取功能开关状态
            features = self.config.get('features', {})
            
            # 视频任务功能开关
            video_tasks_enabled = features.get('video_tasks', {}).get('enabled', False)
            get_video_reviewers_enabled = features.get('video_tasks', {}).get('get_video_reviewers', False)
            follow_video_fans_enabled = features.get('video_tasks', {}).get('follow_video_fans', False)
            
            # 关注列表任务功能开关
            follow_list_tasks_enabled = features.get('follow_list_tasks', {}).get('enabled', False)
            check_follows_enabled = features.get('follow_list_tasks', {}).get('check_follows', False)
            unfollow_enabled = features.get('follow_list_tasks', {}).get('unfollow_users', False)
            
            # 粉丝列表任务功能开关
            fan_list_tasks_enabled = features.get('fan_list_tasks', {}).get('enabled', False)
            check_fans_enabled = features.get('fan_list_tasks', {}).get('check_fans', False)
            follow_back_enabled = features.get('fan_list_tasks', {}).get('follow_back', False)
            fan_interaction_enabled = features.get('fan_list_tasks', {}).get('fan_interaction', False)
            
            logger.info(
                f"功能开关状态:\n"
                f"视频任务: 总开关={video_tasks_enabled}, 提取评论用户={get_video_reviewers_enabled}, 关注视频评论者={follow_video_fans_enabled}\n"
                f"关注列表任务: 总开关={follow_list_tasks_enabled}, 检查关注列表={check_follows_enabled}, 取关={unfollow_enabled}\n"
                f"粉丝列表任务: 总开关={fan_list_tasks_enabled}, 检查粉丝列表={check_fans_enabled}, 回关={follow_back_enabled}, 粉丝私信互动={fan_interaction_enabled}"
            )
            
            # 记录是否执行了视频相关任务
            video_tasks_executed = False
            
            #=============================================
            # 1. 视频任务
            #=============================================
            if video_tasks_enabled:
                logger.info("开始执行视频任务...")
                
                # 第一步：执行视频评论和提取用户任务
                if get_video_reviewers_enabled:
                    logger.info("第一步：执行视频评论和提取用户任务")
                    try:
                        result = self.video_comment_manager.run_video_comment_task()
                        if not result['success']:
                            logger.error("视频评论任务执行失败")
                            return {'success': False, 'reason': '视频访问或评论失败'}
                        logger.info("视频评论任务执行成功")
                        video_tasks_executed = True
                    except Exception as e:
                        logger.error(f"执行视频评论任务时出错: {str(e)}")
                        self.handle_task_failure("执行视频评论任务时出错", e, "video_comment_task_error")
                else:
                    logger.info("视频评论和提取用户功能已禁用，跳过任务")
                
                # 第二步：执行关注视频评论者任务
                if follow_video_fans_enabled:
                    logger.info("第二步：执行关注视频评论者任务")
                    try:
                        # 更新配置中的视频关注开关
                        self.follow_fans_manager.config['features'] = {
                            'follow_video_fans': follow_video_fans_enabled
                        }
                        
                        task_result = self.follow_fans_manager.run_follow_fans_task()
                        if task_result:
                            logger.info("关注视频评论者任务执行成功")
                        else:
                            logger.error("关注视频评论者任务执行失败")
                            return {'success': False, 'reason': '关注视频评论者任务失败'}
                        video_tasks_executed = True
                    except Exception as e:
                        logger.error(f"执行关注视频评论者任务时出错: {str(e)}")
                        self.handle_task_failure("执行关注视频评论者任务时出错", e, "follow_fans_task_error")
                else:
                    logger.info("关注视频评论者功能已禁用，跳过任务")
            else:
                logger.info("视频任务功能已禁用，跳过所有视频相关任务")
            
            #=============================================
            # 2. 关注列表任务
            #=============================================
            # 如果执行了视频相关任务，则不执行关注列表相关任务
            if video_tasks_executed:
                logger.info("已执行视频相关任务，跳过关注列表相关任务")
            elif follow_list_tasks_enabled:
                logger.info("开始执行关注列表任务...")
                
                # 第三步：执行取关任务
                if unfollow_enabled:
                    logger.info("第三步：执行取关任务")
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
                        self.handle_task_failure("执行取关任务时出错", e, "unfollow_task_error")
                else:
                    logger.info("取关功能已禁用，跳过取关任务")
                
                # 第四步：执行检查关注列表任务
                if check_follows_enabled:
                    logger.info("第四步：执行检查关注列表任务")
                    try:
                        if self.follow_list_manager.run_check_follows_task():
                            # 获取配置的任务间隔时间
                            task_interval = self.config.get('operation', {}).get('common', {}).get('task_interval', 3600)  # 默认1小时
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
                        self.handle_task_failure("执行检查关注列表任务时出错", e, "check_follows_task_error")
                else:
                    logger.info("检查关注列表功能已禁用，跳过检查关注列表任务")
            else:
                logger.info("关注列表任务功能已禁用，跳过所有关注列表相关任务")
            
            #=============================================
            # 3. 粉丝列表任务
            #=============================================
            if fan_list_tasks_enabled:
                logger.info("开始执行粉丝列表任务...")
                
                # 第五步：执行检查粉丝列表任务
                if check_fans_enabled:
                    logger.info("第五步：执行检查粉丝列表任务")
                    try:
                        if self.fan_manager.run_check_fans_task():
                            logger.info("检查粉丝列表任务执行成功")
                        else:
                            logger.warning("检查粉丝列表任务执行失败，检查浏览器状态")
                            if not self.browser_manager.check_and_restart_browser():
                                logger.error("浏览器状态异常，无法继续执行任务")
                                return {'success': False, 'reason': '浏览器状态异常'}
                    except Exception as e:
                        logger.error(f"执行检查粉丝列表任务时出错: {str(e)}")
                        self.handle_task_failure("执行检查粉丝列表任务时出错", e, "check_fans_task_error")
                else:
                    logger.info("检查粉丝列表功能已禁用，跳过检查粉丝列表任务")
                
                # 第六步：执行回关任务
                if follow_back_enabled:
                    logger.info("第六步：执行回关任务")
                    try:
                        if self.fan_manager.run_follow_back_task():
                            logger.info("回关任务执行成功")
                        else:
                            logger.warning("回关任务执行失败，检查浏览器状态")
                            if not self.browser_manager.check_and_restart_browser():
                                logger.error("浏览器状态异常，无法继续执行任务")
                                return {'success': False, 'reason': '浏览器状态异常'}
                    except Exception as e:
                        logger.error(f"执行回关任务时出错: {str(e)}")
                        self.handle_task_failure("执行回关任务时出错", e, "follow_back_task_error")
                else:
                    logger.info("回关功能已禁用，跳过回关任务")
                
                # 第七步：执行粉丝私信互动任务
                if fan_interaction_enabled:
                    logger.info("第七步：执行粉丝私信互动任务")
                    try:
                        if self.fan_manager.run_fan_interaction_task():
                            logger.info("粉丝私信互动任务执行成功")
                        else:
                            logger.warning("粉丝私信互动任务执行失败，检查浏览器状态")
                            if not self.browser_manager.check_and_restart_browser():
                                logger.error("浏览器状态异常，无法继续执行任务")
                                return {'success': False, 'reason': '浏览器状态异常'}
                    except Exception as e:
                        logger.error(f"执行粉丝私信互动任务时出错: {str(e)}")
                        self.handle_task_failure("执行粉丝私信互动任务时出错", e, "fan_interaction_task_error")
                else:
                    logger.info("粉丝私信互动功能已禁用，跳过私信互动任务")
            else:
                logger.info("粉丝列表任务功能已禁用，跳过所有粉丝列表相关任务")
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"执行任务时出错: {str(e)}")
            return {'success': False, 'error': str(e)}
        
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
            max_unfollow_per_day = self.config.get('operation', {}).get('follow_list_tasks', {}).get('daily_unfollow_limit', 100)
            unfollow_count_today = self.db.get_today_unfollow_count()
            remaining_unfollow = max_unfollow_per_day - unfollow_count_today
            
            logger.info(f"今日剩余可取关数量: {remaining_unfollow}")
            
            if remaining_unfollow <= 0:
                logger.info("今日取关数量已达上限，跳过取关任务")
                return True
            
            # 获取取关天数阈值
            unfollow_days = self.config.get('operation', {}).get('follow_list_tasks', {}).get('unfollow_days', 3)
            
            # 获取需要取关的用户
            users_to_unfollow = self.db.get_users_to_unfollow(remaining_unfollow, unfollow_days)
            
            if not users_to_unfollow:
                logger.info("没有找到需要取关的用户")
                return True
            
            logger.info(f"找到 {len(users_to_unfollow)} 个需要取关的用户")
            
            # 分批处理取关用户
            batch_size = self.config.get('operation', {}).get('follow_list_tasks', {}).get('unfollow_batch_size', 10)
            total_success_count = 0  # 总成功数
            
            for i in range(0, len(users_to_unfollow), batch_size):
                batch = users_to_unfollow[i:i+batch_size]
                current_batch = i//batch_size + 1
                total_batches = (len(users_to_unfollow) + batch_size - 1) // batch_size
                logger.info(f"[批次 {current_batch}/{total_batches}] 开始处理取关用户，本批 {len(batch)} 个")
                
                batch_success_count = 0  # 当前批次成功数
                current_count = 0
                batch_total = len(batch)
                
                for user in batch:
                    current_count += 1
                    total_progress = f"[总进度 {i + current_count}/{len(users_to_unfollow)}]"
                    batch_progress = f"[批次 {current_batch}/{total_batches} - {current_count}/{batch_total}]"
                    
                    try:
                        # 检查浏览器状态，确保会话有效
                        if not self.browser_manager.is_browser_alive():
                            logger.error(f"{total_progress} {batch_progress} 浏览器会话已断开，重新启动浏览器")
                            if not self.browser_manager.restart_browser():
                                logger.error(f"{total_progress} {batch_progress} 重启浏览器失败，取消当前取关任务")
                                return False
                        
                        logger.info(f"{total_progress} {batch_progress} 准备取关用户: {user['username']} ({user['user_id']})")
                        
                        # 访问用户页面
                        user_url = f"https://www.douyin.com/user/{user['user_id']}"
                        logger.info(f"{total_progress} {batch_progress} 访问用户页面: {user_url}")
                        
                        try:
                            self.driver.get(user_url)
                            time.sleep(3)  # 等待页面加载
                        except Exception as e:
                            logger.error(f"{total_progress} {batch_progress} 访问用户页面失败: {str(e)}")
                            # 检查浏览器状态，如果会话已断开则重启
                            if "invalid session id" in str(e):
                                logger.error(f"{total_progress} {batch_progress} 浏览器会话已断开，尝试重启浏览器")
                                if not self.browser_manager.restart_browser():
                                    logger.error(f"{total_progress} {batch_progress} 重启浏览器失败，取消当前取关任务")
                                    return False
                                continue  # 跳过当前用户，处理下一个
                        
                        # 执行取关操作
                        if self.follow_manager.unfollow_user(user['username'], user['user_id']):
                            batch_success_count += 1
                            total_success_count += 1
                            logger.info(f"{total_progress} {batch_progress} 成功取关用户: {user['username']} ({user['user_id']})")
                        else:
                            logger.warning(f"{total_progress} {batch_progress} 取关用户失败: {user['username']} ({user['user_id']})")
                        
                        # 随机等待一段时间再处理下一个用户
                        wait_time = random.uniform(
                            self.config.get('operation', {}).get('follow_list_tasks', {}).get('unfollow_interval', [5, 15])[0],
                            self.config.get('operation', {}).get('follow_list_tasks', {}).get('unfollow_interval', [5, 15])[1]
                        )
                        if current_count < batch_total:  # 如果不是批次的最后一个用户
                            logger.info(f"{total_progress} {batch_progress} 等待 {wait_time:.2f} 秒后处理下一个用户")
                            time.sleep(wait_time)
                        
                    except Exception as e:
                        logger.error(f"{total_progress} {batch_progress} 处理取关用户失败: {user['username']} ({user['user_id']}), 错误: {str(e)}")
                        # 检查是否是会话失效错误
                        if "invalid session id" in str(e):
                            logger.error(f"{total_progress} {batch_progress} 浏览器会话已断开，尝试重启浏览器")
                            if not self.browser_manager.restart_browser():
                                logger.error(f"{total_progress} {batch_progress} 重启浏览器失败，取消当前取关任务")
                                return False
                        
                        # 继续处理下一个用户
                        if current_count < batch_total:  # 如果不是批次的最后一个用户
                            wait_time = random.uniform(
                                self.config.get('operation', {}).get('follow_list_tasks', {}).get('unfollow_interval', [5, 15])[0],
                                self.config.get('operation', {}).get('follow_list_tasks', {}).get('unfollow_interval', [5, 15])[1]
                            )
                            logger.info(f"{total_progress} {batch_progress} 等待 {wait_time:.2f} 秒后处理下一个用户")
                            time.sleep(wait_time)
                
                # 计算批次成功率
                batch_success_rate = batch_success_count / len(batch) if batch else 0
                logger.info(f"[批次 {current_batch}/{total_batches}] 完成处理，成功率: {batch_success_rate:.2%} ({batch_success_count}/{batch_total})")
            
            # 计算总成功率
            total_success_rate = total_success_count / len(users_to_unfollow) if users_to_unfollow else 0
            logger.info(f"取关任务完成，总成功率: {total_success_rate:.2%}，共处理 {len(users_to_unfollow)} 个用户，成功取关 {total_success_count} 个")
            
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

    def run_check_follows_task(self):
        """
        执行检查关注列表任务
        """
        try:
            logger.info("开始执行检查关注列表任务...")
            
            # 检查浏览器状态
            if not self.browser_manager.check_and_restart_browser():
                logger.error("浏览器状态异常，无法执行检查关注列表任务")
                return False
            
            # 获取配置的任务间隔时间
            task_interval = self.config.get('operation', {}).get('common', {}).get('task_interval', 3600)  # 默认1小时
            
            if self.follow_list_manager.run_check_follows_task():
                logger.info(f"检查关注列表任务完成，休息 {task_interval} 秒后执行下一轮任务")
                return True
            else:
                logger.warning("检查关注列表任务执行失败，检查浏览器状态")
                if not self.browser_manager.check_and_restart_browser():
                    logger.error("浏览器状态异常，无法继续执行任务")
                    return False
            
            return False
        except Exception as e:
            logger.error(f"执行检查关注列表任务时出错: {str(e)}")
            self.handle_task_failure("执行检查关注列表任务时出错", e)
            return False

    def run_check_fans_task(self):
        """
        执行检查粉丝列表任务
        """
        try:
            logger.info("开始执行检查粉丝列表任务...")
            
            # 检查浏览器状态
            if not self.browser_manager.check_and_restart_browser():
                logger.error("浏览器状态异常，无法执行检查粉丝列表任务")
                return False
            
            if self.fan_manager.run_check_fans_task():
                logger.info("检查粉丝列表任务执行成功")
                return True
            else:
                logger.warning("检查粉丝列表任务执行失败，检查浏览器状态")
                if not self.browser_manager.check_and_restart_browser():
                    logger.error("浏览器状态异常，无法继续执行任务")
                    return False
            
            return False
        except Exception as e:
            logger.error(f"执行检查粉丝列表任务时出错: {str(e)}")
            self.handle_task_failure("执行检查粉丝列表任务时出错", e)
            return False

    def run_follow_back_task(self):
        """
        执行回关任务
        """
        try:
            logger.info("开始执行回关任务...")
            
            # 检查浏览器状态
            if not self.browser_manager.check_and_restart_browser():
                logger.error("浏览器状态异常，无法执行回关任务")
                return False
            
            if self.fan_manager.run_follow_back_task():
                logger.info("回关任务执行成功")
                return True
            else:
                logger.warning("回关任务执行失败，检查浏览器状态")
                if not self.browser_manager.check_and_restart_browser():
                    logger.error("浏览器状态异常，无法继续执行任务")
                    return False
            
            return False
        except Exception as e:
            logger.error(f"执行回关任务时出错: {str(e)}")
            self.handle_task_failure("执行回关任务时出错", e)
            return False