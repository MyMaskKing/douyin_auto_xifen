"""
视频评论管理模块

该模块提供了对视频进行评论和提取评论者的功能。
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import random
import time
from .logger import logger, save_screenshot
from .selectors import VIDEO_COMMENT_USER

class VideoCommentManager:
    """视频评论管理类，负责对视频进行评论和提取评论者"""
    
    def __init__(self, browser_manager, db, config):
        """
        初始化视频评论管理器
        
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
    
    def comment_and_extract_users(self, video_url):
        """
        对视频进行评论并提取评论者
        
        参数:
            video_url: 视频完整链接，例如：https://v.douyin.com/i5bgab8q/
            
        返回:
            bool: 是否成功执行
        """
        try:
            # 1. 访问视频页面
            logger.info(f"访问视频页面: {video_url}")
            self.driver.get(video_url)
            self.random_sleep(5, 8)
            
            # 检查页面是否正确加载
            try:
                # 等待视频播放器加载
                video_container = self.wait.until(lambda d: d.find_element(By.CLASS_NAME, "pMZsZmuc"))
                if not video_container:
                    raise Exception("未找到视频容器")
                    
                # 等待视频元素加载
                video_element = self.wait.until(lambda d: d.find_element(By.TAG_NAME, "video"))
                if not video_element:
                    raise Exception("未找到视频元素")
                    
                logger.info("视频页面加载成功")
            except Exception as e:
                logger.error(f"视频页面加载失败: {str(e)}")
                save_screenshot(self.driver, "video_load_error")
                return False
            
            # 检查是否是错误页面
            if "页面不存在" in self.driver.page_source or "视频不存在" in self.driver.page_source:
                logger.error(f"视频不存在或已被删除: {video_url}")
                save_screenshot(self.driver, "video_not_exist")
                return False
            
            # 保存页面截图
            save_screenshot(self.driver, "video_comment", level="NORMAL")
            
            # 2. 点击评论按钮并发送评论
            comment_text = "新人涨粉，互关必回"
            
            # 查找评论输入框
            try:
                # 等待评论输入框容器加载
                comment_container = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "comment-input-inner-container"))
                )
                
                # 点击输入框激活它
                comment_container.click()
                self.random_sleep(1, 2)
                
                # 找到实际的输入区域
                editor = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "public-DraftEditor-content"))
                )
                
                # 模拟真实的键盘输入
                # 先清空输入框
                editor.clear()
                self.random_sleep(0.5, 1)
                
                # 逐个字符输入，模拟真实打字
                for char in comment_text:
                    editor.send_keys(char)
                    self.random_sleep(0.1, 0.3)  # 每个字符之间添加随机延迟
                
                logger.info("找到评论输入框并输入内容")
                self.random_sleep(1, 2)
            except Exception as e:
                logger.error(f"未找到评论输入框或输入失败: {str(e)}")
                save_screenshot(self.driver, "comment_input_error")
                return False
            
            # 查找发送按钮
            try:
                # 等待发送按钮出现并且可点击
                send_button = self.wait.until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "NUzvFSPe"))
                )
                
                # 使用JavaScript点击按钮
                self.driver.execute_script("arguments[0].click();", send_button)
                logger.info("点击发送按钮")
                self.random_sleep(2, 3)
                
                # 检查是否出现验证码或其他异常
                try:
                    # 等待发送按钮消失，确认发送成功
                    self.wait.until_not(
                        EC.presence_of_element_located((By.CLASS_NAME, "NUzvFSPe"))
                    )
                    logger.info("评论发送成功")
                except:
                    logger.warning("评论发送状态未知，可能需要人工验证")
                    save_screenshot(self.driver, "comment_send_status")
                    
                    # 等待用户确认
                    user_input = input("请检查评论是否发送成功，如果需要验证码请完成验证。是否继续？(y/n): ")
                    if user_input.lower() != 'y':
                        logger.info("用户选择终止当前视频的处理")
                        return False
                    else:
                        logger.info("用户确认继续执行")
                
            except Exception as e:
                logger.warning(f"发送评论遇到异常: {str(e)}")
                save_screenshot(self.driver, "send_comment_error")
                
                # 等待用户确认
                user_input = input("发送评论遇到问题，是否重试？(y/n): ")
                if user_input.lower() != 'y':
                    logger.info("用户选择终止当前视频的处理")
                    return False
                else:
                    logger.info("用户选择重试")
                    # 重新尝试发送评论
                    try:
                        send_button = self.wait.until(
                            EC.element_to_be_clickable((By.CLASS_NAME, "NUzvFSPe"))
                        )
                        self.driver.execute_script("arguments[0].click();", send_button)
                        logger.info("重新尝试点击发送按钮")
                    except:
                        logger.error("重试发送评论失败")
                        return False
            
            # 3. 提取评论用户
            max_extract = self.config.get('operation', {}).get('max_follow_per_video', 20)  # 从配置中获取每个视频最多提取的评论数
            extracted_users = 0
            max_scroll = 100  # 增加最大滚动次数以获取更多评论
            scroll_count = 0
            processed_users = set()  # 用于去重
            
            # 获取配置中的最小提取用户数
            min_extract_users = self.config.get('operation', {}).get('min_extract_users_per_video', 5)
            
            while extracted_users < max_extract and scroll_count < max_scroll:
                # 获取当前页面上的评论用户
                comment_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'comment-item')]")
                
                if not comment_elements:
                    logger.warning("未找到评论元素")
                    continue
                
                for comment_element in comment_elements:
                    try:
                        # 提取用户ID和用户名
                        user_id = None
                        username = None
                        
                        # 尝试获取用户链接和ID
                        try:
                            user_link = comment_element.find_element(By.XPATH, ".//a[contains(@href, '/user/')]")
                            if user_link:
                                user_href = user_link.get_attribute("href")
                                user_id = user_href.split("/user/")[1].split("?")[0]
                        except:
                            continue
                        
                        # 尝试获取用户名
                        try:
                            username = user_link.text.strip()
                        except:
                            continue
                        
                        # 添加到follow_fans表
                        if user_id and username and user_id not in processed_users:
                            processed_users.add(user_id)  # 记录已处理的用户ID
                            if self.db.add_follow_fan(user_id, username, "video_comment", video_url):
                                extracted_users += 1
                                logger.info(f"已提取评论用户 {extracted_users}/{max_extract}: {username} ({user_id})")
                        
                        # 如果已经提取足够数量的用户，则退出
                        if extracted_users >= max_extract:
                            break
                    except Exception as e:
                        logger.warning(f"提取评论用户失败: {str(e)}")
                        continue
                
                # 如果已经提取足够数量的用户，则退出
                if extracted_users >= max_extract:
                    break
                
                # 滚动加载更多评论
                logger.info(f"滚动加载更多评论 ({scroll_count+1}/{max_scroll})")
                try:
                    # 尝试滚动评论列表
                    self.driver.execute_script("document.querySelector('.comment-list').scrollTop += 1000;")
                except:
                    # 如果失败，尝试滚动整个页面
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.random_sleep(2, 3)
                scroll_count += 1
            
            logger.info(f"成功从视频 {video_url} 中提取 {extracted_users} 个评论用户")
            
            # 只有当提取到足够数量的用户时，才标记视频为已处理
            if extracted_users >= min_extract_users:
                logger.info(f"已达到最小提取用户数 {min_extract_users}，标记视频为已处理")
                self.db.mark_video_processed(video_url)
                return True
            else:
                logger.warning(f"提取的用户数 {extracted_users} 小于最小要求 {min_extract_users}，视频将不会被标记为已处理")
                return False
            
        except Exception as e:
            logger.error(f"评论视频并提取用户失败: {str(e)}")
            save_screenshot(self.driver, "video_comment_error")
            return False
    
    def run_video_comment_task(self):
        """
        执行视频评论任务
        
        功能：进入到指定的抖音视频中，对视频进行评论。
        
        返回:
            dict: 包含任务执行结果的字典
                {
                    'success': bool,  # 是否成功
                    'reason': str,    # 失败原因（如果失败）
                }
        """
        try:
            # 获取目标视频列表
            target_videos = self.config.get('target_videos', [])
            if not target_videos:
                logger.warning("未配置目标视频")
                return {'success': False, 'reason': '未配置目标视频'}
            
            # 获取第一个未处理的视频
            for video_url in target_videos:
                # 检查是否已经处理过该视频
                if not self.db.is_video_processed(video_url):
                    # 执行评论和提取用户
                    if self.comment_and_extract_users(video_url):
                        # 注意：视频处理状态的更新已经移到comment_and_extract_users方法中
                        # 只有在成功提取评论用户后才会标记为已处理
                        return {'success': True}
                    else:
                        return {'success': False, 'reason': f'处理视频失败: {video_url}'}
            
            # 所有视频都已处理完
            logger.info("所有视频都已处理完毕")
            return {'success': True}
            
        except Exception as e:
            error_msg = f"执行视频评论任务失败: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'reason': error_msg} 