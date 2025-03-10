"""
粉丝关注管理模块

该模块提供了关注视频评论者和群组成员的功能。
"""

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
import random
from .logger import logger, save_screenshot, save_html, get_log_path
import re
from datetime import datetime

class FollowFansManager:
    """粉丝关注管理类，负责关注视频评论者和群组成员"""
    
    def __init__(self, browser_manager, db, config):
        """
        初始化粉丝关注管理器
        
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
    
    def run_follow_fans_task(self):
        """
        执行关注粉丝任务
        
        功能1：进入到指定的抖音视频中，对评论里面所有的人进行关注
        功能2：进入到指定的抖音群中，对群里面所有的人进行关注。
        
        参数说明：
        - target_videos：配置文件中设置的目标视频列表。
        - target_groups：配置文件中设置的目标群组列表。
        - max_follow_per_video：每个视频最多关注的用户数量。
        - max_follow_per_group：每个群组最多关注的用户数量。
        - follow_interval：两次关注操作之间的最小时间间隔（秒）。
        
        返回：
        - 成功返回True，失败返回False。
        - 返回的数据包括每个视频和群组成功关注的用户数量。
        """
        try:
            logger.info("开始执行关注粉丝任务...")
            
            # 获取功能开关配置
            features = self.config.get('features', {})
            follow_video_fans_enabled = features.get('follow_video_fans', False)
            follow_group_fans_enabled = features.get('follow_group_fans', False)
            
            logger.info(f"功能开关状态: 关注视频评论者={follow_video_fans_enabled}, 关注群组成员={follow_group_fans_enabled}")
            
            # 如果两个功能都禁用，则直接返回
            if not follow_video_fans_enabled and not follow_group_fans_enabled:
                logger.info("关注视频评论者和群组成员功能均已禁用，跳过关注粉丝任务")
                return True
            
            # 获取配置参数
            max_follow_per_day = self.config.get('operation', {}).get('daily_follow_limit', 150)
            follow_interval = self.config.get('operation', {}).get('follow_interval', 30)
            max_follow_per_video = self.config.get('operation', {}).get('max_follow_per_video', 20)
            max_follow_per_group = self.config.get('operation', {}).get('max_follow_per_group', 20)
            
            # 检查今日关注数量是否已达上限
            today_follows = self.db.get_today_follow_count()
            
            if today_follows >= max_follow_per_day:
                logger.info(f"今日关注数量 ({today_follows}) 已达上限 ({max_follow_per_day})，跳过关注粉丝任务")
                return True
            
            # 计算今日可关注的数量
            remaining_follows = max_follow_per_day - today_follows
            logger.info(f"今日已关注: {today_follows}, 上限: {max_follow_per_day}, 剩余可关注: {remaining_follows}")
            
            # 处理目标视频
            if follow_video_fans_enabled and remaining_follows > 0:
                # 获取目标视频列表
                target_videos = self.config.get('target_videos', [])
                
                if not target_videos:
                    logger.warning("未配置目标视频，跳过视频评论关注任务")
                else:
                    logger.info(f"开始处理目标视频，共 {len(target_videos)} 个")
                    
                    # 获取未处理的目标视频
                    unprocessed_videos = self.db.get_unprocessed_target_videos(target_videos)
                    
                    if unprocessed_videos:
                        # 随机选择一个目标视频
                        target_video = random.choice(unprocessed_videos)
                        logger.info(f"选择目标视频: {target_video}")
                        
                        # 关注视频评论者
                        follow_count = self.follow_video_commenters(target_video, min(remaining_follows, max_follow_per_video))
                        
                        # 更新剩余可关注数量
                        remaining_follows -= follow_count
                        
                        # 标记视频为已处理
                        self.db.mark_target_video_processed(target_video, follow_count)
                        logger.info(f"目标视频 {target_video} 已处理, 关注了 {follow_count} 个评论者")
                    else:
                        logger.info("所有目标视频今日已处理，跳过视频处理")
            
            # 处理目标群组
            if follow_group_fans_enabled and remaining_follows > 0:
                # 获取目标群组列表
                target_groups = self.config.get('target_groups', [])
                
                if not target_groups:
                    logger.warning("未配置目标群组，跳过群组成员关注任务")
                else:
                    logger.info(f"开始处理目标群组，共 {len(target_groups)} 个")
                    
                    # 获取未处理的目标群组
                    unprocessed_groups = self.db.get_unprocessed_target_groups(target_groups)
                    
                    if unprocessed_groups:
                        # 随机选择一个目标群组
                        target_group = random.choice(unprocessed_groups)
                        logger.info(f"选择目标群组: {target_group}")
                        
                        # 关注群组成员
                        follow_count = self.follow_group_members(target_group, min(remaining_follows, max_follow_per_group))
                        
                        # 更新剩余可关注数量
                        remaining_follows -= follow_count
                        
                        # 标记群组为已处理
                        self.db.mark_target_group_processed(target_group, follow_count)
                        logger.info(f"目标群组 {target_group} 已处理, 关注了 {follow_count} 个成员")
                    else:
                        logger.info("所有目标群组今日已处理，跳过群组处理")
            
            # 返回个人主页
            self.driver.get("https://www.douyin.com/user/self")
            self.random_sleep(2, 3)
            
            return True
        except Exception as e:
            logger.error(f"关注粉丝任务失败: {str(e)}")
            save_screenshot(self.driver, "follow_fans_error")
            return False
    
    def follow_video_commenters(self, video_id, max_follows):
        """
        关注视频评论者
        
        参数:
            video_id: 视频ID
            max_follows: 最大关注数量
            
        返回:
            成功关注的用户数量
        """
        try:
            # 访问视频页面
            logger.info(f"访问视频页面: {video_id}")
            self.driver.get(f"https://www.douyin.com/video/{video_id}")
            self.random_sleep(5, 8)
            
            # 保存页面截图
            save_screenshot(self.driver, f"video_{video_id}", level="NORMAL")
            
            # 滚动到评论区
            logger.info("滚动到评论区")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            self.random_sleep(2, 3)
            
            # 查找评论区
            comment_area = None
            comment_area_selectors = [
                "//div[contains(@class, 'comment-area')]",
                "//div[contains(@class, 'comment-list')]",
                "//div[contains(@class, 'comment-container')]"
            ]
            
            for selector in comment_area_selectors:
                try:
                    comment_area = self.driver.find_element(By.XPATH, selector)
                    logger.info(f"找到评论区: {selector}")
                    break
                except:
                    continue
            
            if not comment_area:
                logger.warning("未找到评论区，尝试点击评论按钮")
                
                # 尝试点击评论按钮
                comment_button_selectors = [
                    "//button[contains(., '评论')]",
                    "//div[contains(@class, 'comment-button')]",
                    "//div[contains(@class, 'comment-icon')]"
                ]
                
                for selector in comment_button_selectors:
                    try:
                        comment_button = self.driver.find_element(By.XPATH, selector)
                        comment_button.click()
                        logger.info(f"点击评论按钮: {selector}")
                        self.random_sleep(2, 3)
                        break
                    except:
                        continue
            
            # 加载更多评论
            logger.info("加载更多评论")
            for _ in range(5):  # 最多滚动5次
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.random_sleep(2, 3)
            
            # 获取评论项
            comment_items = []
            comment_item_selectors = [
                "//div[contains(@class, 'comment-item')]",
                "//div[contains(@class, 'comment-card')]",
                "//div[contains(@class, 'comment-container')]//div[contains(@class, 'user-info')]"
            ]
            
            for selector in comment_item_selectors:
                try:
                    items = self.driver.find_elements(By.XPATH, selector)
                    if items:
                        logger.info(f"使用选择器 '{selector}' 找到 {len(items)} 个评论项")
                        comment_items = items
                        break
                except Exception as e:
                    logger.warning(f"使用选择器 '{selector}' 查找评论项失败: {str(e)}")
            
            if not comment_items:
                logger.warning("未找到任何评论项")
                return 0
            
            # 关注评论者
            follow_count = 0
            
            for i, comment_item in enumerate(comment_items):
                if follow_count >= max_follows:
                    logger.info(f"已达到最大关注数量: {max_follows}")
                    break
                
                try:
                    # 提取用户信息
                    username = None
                    user_id = None
                    
                    # 提取用户名
                    username_selectors = [
                        ".//span[contains(@class, 'user-name')]",
                        ".//span[contains(@class, 'nickname')]",
                        ".//a[contains(@href, '/user/')]"
                    ]
                    
                    for selector in username_selectors:
                        try:
                            username_element = comment_item.find_element(By.XPATH, selector)
                            username = username_element.text.strip()
                            if username:
                                break
                        except:
                            continue
                    
                    if not username:
                        logger.warning(f"无法获取第 {i+1} 个评论者的用户名，跳过")
                        continue
                    
                    # 提取用户ID
                    try:
                        link_element = comment_item.find_element(By.XPATH, ".//a[contains(@href, '/user/')]")
                        href = link_element.get_attribute('href')
                        if href and '/user/' in href:
                            user_id = href.split('/user/')[-1].split('?')[0]
                        else:
                            logger.warning(f"无法从链接提取用户ID: {href}")
                            continue
                    except:
                        logger.warning(f"无法获取用户 {username} 的ID，跳过")
                        continue
                    
                    # 检查是否已关注
                    if self.db.is_followed(user_id):
                        logger.info(f"已关注用户: {username} ({user_id}), 跳过")
                        continue
                    
                    # 查找关注按钮
                    follow_button = None
                    button_selectors = [
                        ".//button[contains(., '关注')]",
                        ".//div[contains(@class, 'follow-button')]",
                        ".//div[@data-e2e='user-info-follow']"
                    ]
                    
                    for selector in button_selectors:
                        try:
                            buttons = comment_item.find_elements(By.XPATH, selector)
                            for button in buttons:
                                if '关注' in button.text and '已关注' not in button.text and '互相关注' not in button.text:
                                    follow_button = button
                                    break
                            if follow_button:
                                break
                        except:
                            continue
                    
                    if not follow_button:
                        logger.warning(f"未找到用户 {username} 的关注按钮，可能已关注或页面结构变化")
                        continue
                    
                    # 点击关注按钮
                    logger.info(f"点击关注按钮，关注用户 {username}")
                    try:
                        follow_button.click()
                        self.random_sleep(1, 2)
                    except:
                        # 尝试使用JavaScript点击
                        try:
                            self.driver.execute_script("arguments[0].click();", follow_button)
                            self.random_sleep(1, 2)
                        except Exception as e:
                            logger.error(f"点击关注按钮失败: {str(e)}")
                            continue
                    
                    # 检查是否出现确认弹窗，如果有则点击确认
                    try:
                        confirm_button = self.driver.find_element(By.XPATH, "//button[contains(., '确定')]")
                        confirm_button.click()
                        self.random_sleep(1, 2)
                    except:
                        # 没有确认弹窗，继续执行
                        pass
                    
                    # 标记用户为已关注
                    self.db.mark_user_followed(user_id, username)
                    follow_count += 1
                    
                    logger.info(f"成功关注用户 {username} ({user_id})，当前进度: {follow_count}/{max_follows}")
                    
                    # 等待指定时间间隔
                    follow_interval = self.config.get('operation', {}).get('follow_interval', 30)
                    self.random_sleep(follow_interval, follow_interval + 10)
                except Exception as e:
                    logger.error(f"处理评论项时出错: {str(e)}")
                    continue
            
            logger.info(f"视频 {video_id} 评论者关注完成，共关注 {follow_count} 个用户")
            return follow_count
        except Exception as e:
            logger.error(f"关注视频评论者失败: {str(e)}")
            save_screenshot(self.driver, f"follow_video_error_{video_id}")
            return 0
    
    def follow_group_members(self, group_id, max_follows):
        """
        关注群组成员
        
        参数:
            group_id: 群组ID
            max_follows: 最大关注数量
            
        返回:
            成功关注的用户数量
        """
        try:
            # 访问群组页面
            logger.info(f"访问群组页面: {group_id}")
            self.driver.get(f"https://www.douyin.com/group/{group_id}")
            self.random_sleep(5, 8)
            
            # 保存页面截图
            save_screenshot(self.driver, f"group_{group_id}", level="NORMAL")
            
            # 点击成员列表按钮
            member_list_button_selectors = [
                "//button[contains(., '成员')]",
                "//div[contains(@class, 'member-button')]",
                "//div[contains(., '成员') and contains(@class, 'tab')]"
            ]
            
            for selector in member_list_button_selectors:
                try:
                    member_button = self.driver.find_element(By.XPATH, selector)
                    member_button.click()
                    logger.info(f"点击成员列表按钮: {selector}")
                    self.random_sleep(2, 3)
                    break
                except:
                    continue
            
            # 获取成员项
            member_items = []
            member_item_selectors = [
                "//div[contains(@class, 'member-item')]",
                "//div[contains(@class, 'user-item')]",
                "//div[contains(@class, 'member-list')]//div[contains(@class, 'user-info')]"
            ]
            
            for selector in member_item_selectors:
                try:
                    items = self.driver.find_elements(By.XPATH, selector)
                    if items:
                        logger.info(f"使用选择器 '{selector}' 找到 {len(items)} 个成员项")
                        member_items = items
                        break
                except Exception as e:
                    logger.warning(f"使用选择器 '{selector}' 查找成员项失败: {str(e)}")
            
            if not member_items:
                logger.warning("未找到任何成员项")
                return 0
            
            # 关注群组成员
            follow_count = 0
            
            for i, member_item in enumerate(member_items):
                if follow_count >= max_follows:
                    logger.info(f"已达到最大关注数量: {max_follows}")
                    break
                
                try:
                    # 提取用户信息
                    username = None
                    user_id = None
                    
                    # 提取用户名
                    username_selectors = [
                        ".//span[contains(@class, 'user-name')]",
                        ".//span[contains(@class, 'nickname')]",
                        ".//a[contains(@href, '/user/')]"
                    ]
                    
                    for selector in username_selectors:
                        try:
                            username_element = member_item.find_element(By.XPATH, selector)
                            username = username_element.text.strip()
                            if username:
                                break
                        except:
                            continue
                    
                    if not username:
                        logger.warning(f"无法获取第 {i+1} 个成员的用户名，跳过")
                        continue
                    
                    # 提取用户ID
                    try:
                        link_element = member_item.find_element(By.XPATH, ".//a[contains(@href, '/user/')]")
                        href = link_element.get_attribute('href')
                        if href and '/user/' in href:
                            user_id = href.split('/user/')[-1].split('?')[0]
                        else:
                            logger.warning(f"无法从链接提取用户ID: {href}")
                            continue
                    except:
                        logger.warning(f"无法获取用户 {username} 的ID，跳过")
                        continue
                    
                    # 检查是否已关注
                    if self.db.is_followed(user_id):
                        logger.info(f"已关注用户: {username} ({user_id}), 跳过")
                        continue
                    
                    # 查找关注按钮
                    follow_button = None
                    button_selectors = [
                        ".//button[contains(., '关注')]",
                        ".//div[contains(@class, 'follow-button')]",
                        ".//div[@data-e2e='user-info-follow']"
                    ]
                    
                    for selector in button_selectors:
                        try:
                            buttons = member_item.find_elements(By.XPATH, selector)
                            for button in buttons:
                                if '关注' in button.text and '已关注' not in button.text and '互相关注' not in button.text:
                                    follow_button = button
                                    break
                            if follow_button:
                                break
                        except:
                            continue
                    
                    if not follow_button:
                        logger.warning(f"未找到用户 {username} 的关注按钮，可能已关注或页面结构变化")
                        continue
                    
                    # 点击关注按钮
                    logger.info(f"点击关注按钮，关注用户 {username}")
                    try:
                        follow_button.click()
                        self.random_sleep(1, 2)
                    except:
                        # 尝试使用JavaScript点击
                        try:
                            self.driver.execute_script("arguments[0].click();", follow_button)
                            self.random_sleep(1, 2)
                        except Exception as e:
                            logger.error(f"点击关注按钮失败: {str(e)}")
                            continue
                    
                    # 检查是否出现确认弹窗，如果有则点击确认
                    try:
                        confirm_button = self.driver.find_element(By.XPATH, "//button[contains(., '确定')]")
                        confirm_button.click()
                        self.random_sleep(1, 2)
                    except:
                        # 没有确认弹窗，继续执行
                        pass
                    
                    # 标记用户为已关注
                    self.db.mark_user_followed(user_id, username)
                    follow_count += 1
                    
                    logger.info(f"成功关注用户 {username} ({user_id})，当前进度: {follow_count}/{max_follows}")
                    
                    # 等待指定时间间隔
                    follow_interval = self.config.get('operation', {}).get('follow_interval', 3)
                    self.random_sleep(follow_interval, follow_interval + 10)
                except Exception as e:
                    logger.error(f"处理成员项时出错: {str(e)}")
                    continue
            
            logger.info(f"群组 {group_id} 成员关注完成，共关注 {follow_count} 个用户")
            return follow_count
        except Exception as e:
            logger.error(f"关注群组成员失败: {str(e)}")
            save_screenshot(self.driver, f"follow_group_error_{group_id}")
            return 0 