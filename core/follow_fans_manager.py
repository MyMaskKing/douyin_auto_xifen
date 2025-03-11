"""
粉丝关注管理模块

该模块提供了对待关注粉丝进行批量关注和发送私信的功能。
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import random
import time
from datetime import datetime
from .logger import logger, save_screenshot

class FollowFansManager:
    """粉丝关注管理类，负责批量关注粉丝和发送私信"""
    
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
    
    def follow_user(self, user_id, username):
        """
        关注指定用户
        
        参数:
            user_id: 用户ID
            username: 用户名
            
        返回:
            bool: 是否成功关注
        """
        try:
            # 访问用户主页
            logger.info(f"访问用户主页: {username} ({user_id})")
            self.driver.get(f"https://www.douyin.com/user/{user_id}")
            self.random_sleep(3, 5)
            
            # 保存页面截图
            save_screenshot(self.driver, f"follow_user_{user_id}", level="NORMAL")
            
            # 查找关注按钮
            follow_button = None
            follow_button_selectors = [
                "//button[contains(., '关注')]",
                "//div[contains(@class, 'follow-button')]",
                "//div[contains(@class, 'focus-button')]"
            ]
            
            for selector in follow_button_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if "已关注" not in element.text and "互相关注" not in element.text:
                            follow_button = element
                            logger.info(f"找到关注按钮: {selector}")
                            break
                    if follow_button:
                        break
                except:
                    continue
            
            if not follow_button:
                logger.warning(f"未找到关注按钮或用户已关注: {username} ({user_id})")
                return False
            
            # 点击关注按钮
            logger.info(f"点击关注按钮: {username} ({user_id})")
            try:
                follow_button.click()
                self.random_sleep(2, 3)
            except:
                # 尝试使用JavaScript点击
                try:
                    self.driver.execute_script("arguments[0].click();", follow_button)
                    self.random_sleep(2, 3)
                except Exception as e:
                    logger.error(f"点击关注按钮失败: {str(e)}")
                    return False
            
            # 检查是否关注成功
            try:
                # 等待关注按钮变为已关注状态
                self.wait.until(lambda d: any(
                    "已关注" in e.text or "互相关注" in e.text 
                    for e in d.find_elements(By.XPATH, "//button[contains(., '关注')] | //div[contains(@class, 'follow-button')] | //div[contains(@class, 'focus-button')]")
                ))
                logger.info(f"成功关注用户: {username} ({user_id})")
                
                # 记录关注
                self.db.add_follow_record(user_id, username)
                
                return True
            except Exception as e:
                logger.warning(f"无法确认关注是否成功: {str(e)}")
                # 尝试再次检查
                time.sleep(3)
                page_source = self.driver.page_source
                if "已关注" in page_source or "互相关注" in page_source:
                    logger.info(f"通过页面源码确认关注成功: {username} ({user_id})")
                    
                    # 记录关注
                    self.db.add_follow_record(user_id, username)
                    
                    return True
                else:
                    logger.error(f"关注可能未成功: {username} ({user_id})")
                    save_screenshot(self.driver, f"follow_user_failed_{user_id}")
                    return False
                
        except Exception as e:
            logger.error(f"关注用户失败: {str(e)}")
            save_screenshot(self.driver, f"follow_user_error_{user_id}")
            return False
    
    def send_message(self, user_id, username, message):
        """
        向指定用户发送私信
        
        参数:
            user_id: 用户ID
            username: 用户名
            message: 私信内容
            
        返回:
            bool: 是否成功发送
        """
        try:
            # 访问用户主页
            logger.info(f"访问用户主页准备发送私信: {username} ({user_id})")
            self.driver.get(f"https://www.douyin.com/user/{user_id}")
            self.random_sleep(3, 5)
            
            # 保存页面截图
            save_screenshot(self.driver, f"send_message_{user_id}", level="NORMAL")
            
            # 查找私信按钮
            message_button = None
            message_button_selectors = [
                "//button[contains(@class, 'K8kpIsJm')]",
                "//button[contains(@class, 'semi-button-secondary')][.//span[text()='私信']]",
                "//button[contains(., '私信')]"
            ]
            
            for selector in message_button_selectors:
                try:
                    message_button = self.driver.find_element(By.XPATH, selector)
                    logger.info(f"找到私信按钮: {selector}")
                    break
                except:
                    continue
            
            if not message_button:
                logger.warning(f"未找到私信按钮: {username} ({user_id})")
                return False
            
            # 点击私信按钮
            logger.info(f"点击私信按钮: {username} ({user_id})")
            try:
                message_button.click()
                self.random_sleep(2, 3)
            except:
                # 尝试使用JavaScript点击
                try:
                    self.driver.execute_script("arguments[0].click();", message_button)
                    self.random_sleep(2, 3)
                except Exception as e:
                    logger.error(f"点击私信按钮失败: {str(e)}")
                    return False
            
            # 查找私信输入框
            message_input = None
            message_input_selectors = [
                "//div[contains(@class, 'public-DraftEditor-content')]",
                "//div[contains(@class, 'DraftEditor-editorContainer')]//div[@contenteditable='true']",
                "//div[contains(@class, 'im-richtext-container')]//div[@contenteditable='true']"
            ]
            
            for selector in message_input_selectors:
                try:
                    message_input = self.driver.find_element(By.XPATH, selector)
                    logger.info(f"找到私信输入框: {selector}")
                    break
                except:
                    continue
            
            if not message_input:
                logger.warning(f"未找到私信输入框: {username} ({user_id})")
                return False
            
            # 输入私信内容
            logger.info(f"输入私信内容: {message}")
            try:
                # 先点击输入框激活它
                message_input.click()
                self.random_sleep(1, 2)
                
                # 清空输入框
                message_input.clear()
                self.random_sleep(0.5, 1)
                
                # 模拟人工输入
                for char in message:
                    message_input.send_keys(char)
                    # 随机等待一个很短的时间，模拟人工输入速度
                    time.sleep(random.uniform(0.1, 0.3))
                
                self.random_sleep(1, 2)
            except Exception as e:
                logger.error(f"输入私信内容失败: {str(e)}")
                return False
            
            # 查找发送按钮
            send_button = None
            send_button_selectors = [
                "//span[contains(@class, 'PygT7Ced') and contains(@class, 'JnY63Rbk') and contains(@class, 'e2e-send-msg-btn')]",
                "//span[contains(@class, 'PygT7Ced')]//svg",
                "//span[contains(@class, 'e2e-send-msg-btn')]"
            ]
            
            for selector in send_button_selectors:
                try:
                    send_button = self.driver.find_element(By.XPATH, selector)
                    logger.info(f"找到发送按钮: {selector}")
                    break
                except:
                    continue
            
            if send_button:
                # 点击发送按钮
                logger.info("点击发送按钮")
                try:
                    # 尝试直接点击
                    send_button.click()
                    self.random_sleep(2, 3)
                except:
                    try:
                        # 如果直接点击失败，尝试点击父元素
                        parent = send_button.find_element(By.XPATH, "..")
                        parent.click()
                        self.random_sleep(2, 3)
                    except:
                        # 如果点击父元素也失败，尝试使用JavaScript点击
                        try:
                            self.driver.execute_script("arguments[0].click();", send_button)
                            self.random_sleep(2, 3)
                        except Exception as e:
                            logger.error(f"点击发送按钮失败: {str(e)}")
                            return False
            else:
                # 如果没有找到发送按钮，尝试按回车键发送
                logger.info("未找到发送按钮，尝试按回车键发送")
                message_input.send_keys(Keys.ENTER)
                self.random_sleep(2, 3)
            
            # 检查是否发送成功
            try:
                # 等待发送按钮变为灰色状态（JnY63Rbk类名消失）
                self.wait.until(lambda d: len(d.find_elements(By.XPATH, "//span[contains(@class, 'PygT7Ced') and contains(@class, 'e2e-send-msg-btn') and not(contains(@class, 'JnY63Rbk'))]")) > 0)
                logger.info(f"成功发送私信给用户: {username} ({user_id})")
                return True
            except Exception as e:
                logger.warning(f"无法确认私信是否发送成功: {str(e)}")
                # 再次检查按钮状态
                try:
                    time.sleep(2)
                    # 如果找到了灰色状态的按钮，说明发送成功
                    if len(self.driver.find_elements(By.XPATH, "//span[contains(@class, 'PygT7Ced') and contains(@class, 'e2e-send-msg-btn') and not(contains(@class, 'JnY63Rbk'))]")) > 0:
                        logger.info(f"通过按钮状态确认私信发送成功: {username} ({user_id})")
                        return True
                except:
                    pass
                return False
                
        except Exception as e:
            logger.error(f"发送私信失败: {str(e)}")
            save_screenshot(self.driver, f"send_message_error_{user_id}")
            return False
    
    def run_follow_fans_task(self):
        """
        执行关注粉丝任务
        
        功能：处理待关注粉丝列表中的用户，进行关注操作。
        主要处理来自视频评论的用户。
        
        返回：
            bool: 任务执行成功返回True，否则返回False
        """
        try:
            logger.info("开始执行关注视频评论者任务...")
            
            # 获取功能开关配置
            features = self.config.get('features', {})
            follow_video_fans_enabled = features.get('follow_video_fans', False)
            
            # 如果功能禁用，则直接返回
            if not follow_video_fans_enabled:
                logger.info("关注视频评论者功能已禁用，跳过任务")
                return True
            
            # 获取配置参数
            batch_size = self.config.get('operation', {}).get('follow_fans_batch_size', 10)
            max_follow_per_day = self.config.get('operation', {}).get('daily_follow_limit', 150)
            message = self.config.get('interaction', {}).get('follow_message', "为了成为有效粉丝，需要进行三天聊天。")
            
            # 获取等待时间配置
            operation_config = self.config.get('operation', {})
            batch_rest_interval = operation_config.get('batch_rest_interval', [30, 60])  # 批量处理后的休息时间，默认30-60秒
            user_interval = operation_config.get('user_interval', [3, 10])  # 单个用户处理后的等待时间，默认3-10秒
            batch_size_before_rest = operation_config.get('batch_size_before_rest', 20)  # 多少个用户后休息，默认20个
            
            # 检查今日关注数量是否已达上限
            today_follows = self.db.get_today_follow_count()
            
            if today_follows >= max_follow_per_day:
                logger.info(f"今日关注数量 ({today_follows}) 已达上限 ({max_follow_per_day})，跳过任务")
                return True
            
            # 计算今日可关注的数量
            remaining_follows = max_follow_per_day - today_follows
            logger.info(f"今日已关注: {today_follows}, 上限: {max_follow_per_day}, 剩余可关注: {remaining_follows}")
            
            # 获取未处理的待关注粉丝（仅视频评论者）
            unprocessed_fans = self.db.get_unprocessed_follow_fans(min(batch_size, remaining_follows))
            
            if not unprocessed_fans:
                logger.info("没有待处理的视频评论者")
                return True
            
            logger.info(f"获取到 {len(unprocessed_fans)} 个待处理的视频评论者")
            
            # 处理待关注粉丝
            success_count = 0
            batch_count = 0  # 记录当前批次处理的数量
            
            for fan in unprocessed_fans:
                fan_id = fan[0]  # 数据库记录ID
                user_id = fan[1]  # 用户ID
                username = fan[2]  # 用户名
                from_type = fan[3]  # 来源类型
                
                # 只处理来自视频评论的用户
                if from_type != 'video_comment':
                    logger.info(f"跳过非视频评论用户: {username} ({from_type})")
                    self.db.mark_follow_fan_as_processed(fan_id)
                    continue
                
                # 检查是否已关注
                if self.db.is_followed(user_id):
                    logger.info(f"用户 {username} 已经关注过，跳过")
                    self.db.mark_follow_fan_as_processed(fan_id)
                    continue
                
                # 关注用户
                follow_success = self.follow_user(user_id, username)
                
                if follow_success:
                    logger.info(f"成功关注视频评论者: {username} ({user_id})")
                    
                    # 发送私信
                    message_success = self.send_message(user_id, username, message)
                    
                    if message_success:
                        logger.info(f"成功发送私信给用户: {username} ({user_id})")
                    else:
                        logger.warning(f"发送私信给用户失败: {username} ({user_id})")
                    
                    # 从follow_fans表中删除
                    self.db.delete_follow_fan(fan_id)
                    
                    success_count += 1
                    batch_count += 1
                else:
                    logger.warning(f"关注视频评论者失败: {username} ({user_id})")
                    # 标记为已处理
                    self.db.mark_follow_fan_as_processed(fan_id)
                
                # 每处理指定数量用户后休息一段时间
                if batch_count >= batch_size_before_rest:
                    if isinstance(batch_rest_interval, list) and len(batch_rest_interval) == 2:
                        rest_time = random.uniform(batch_rest_interval[0], batch_rest_interval[1])
                    else:
                        rest_time = batch_rest_interval
                    logger.info(f"已处理{batch_size_before_rest}个用户，休息 {rest_time:.1f} 秒")
                    time.sleep(rest_time)
                    batch_count = 0  # 重置批次计数
                else:
                    # 每个用户之间短暂等待
                    if isinstance(user_interval, list) and len(user_interval) == 2:
                        wait_time = random.uniform(user_interval[0], user_interval[1])
                    else:
                        wait_time = user_interval
                    logger.info(f"等待 {wait_time:.1f} 秒后处理下一个用户")
                    time.sleep(wait_time)
            
            logger.info(f"关注视频评论者任务完成，成功关注 {success_count} 个用户")
            return True
            
        except Exception as e:
            logger.error(f"执行关注视频评论者任务失败: {str(e)}")
            save_screenshot(self.driver, "follow_video_fans_error")
            return False 