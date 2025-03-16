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
            
            # 2. 等待评论列表加载
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//div[@data-e2e='comment-list']"))
                )
                self.random_sleep(2, 3)
            except Exception as e:
                logger.error(f"评论列表加载失败: {str(e)}")
                return False
            
            # 3. 提取评论用户
            max_extract = self.config.get('operation', {}).get('video_tasks', {}).get('max_follow_per_video', 20)
            extracted_users = 0
            scroll_count = 0
            processed_users = set()
            no_new_data_count = 0
            min_extract_users = self.config.get('operation', {}).get('video_tasks', {}).get('min_extract_users_per_video', 5)
            
            while extracted_users < max_extract and no_new_data_count < 5:
                # 记录当前评论数量
                current_comments = len(self.driver.find_elements(By.XPATH, "//div[@data-e2e='comment-list']//div[@data-e2e='comment-item']"))
                
                # 滚动加载更多评论
                logger.info(f"滚动加载更多评论 ({scroll_count+1})")
                try:
                    # 尝试多种滚动方式
                    scroll_script = """
                    function findScrollContainer() {
                        // 方式1：通过route-scroll-container类查找
                        let container1 = document.querySelector('.route-scroll-container');
                        if (container1) return container1;
                        
                        // 方式2：通过IhmVuo1S类查找
                        let container2 = document.querySelector('.IhmVuo1S');
                        if (container2) return container2;
                        
                        // 方式3：通过comment-list查找
                        let container3 = document.querySelector('[data-e2e="comment-list"]');
                        if (container3) return container3;
                        
                        return null;
                    }
                    
                    let scrollContainer = findScrollContainer();
                    if (scrollContainer) {
                        // 记录当前位置
                        let oldScrollTop = scrollContainer.scrollTop;
                        let oldScrollHeight = scrollContainer.scrollHeight;
                        
                        // 尝试滚动
                        scrollContainer.scrollTop = scrollContainer.scrollHeight;
                        
                        // 如果第一次滚动无效，尝试增加滚动距离
                        if (oldScrollTop === scrollContainer.scrollTop) {
                            scrollContainer.scrollTop += 500;  // 减小滚动距离，避免滚动过快
                        }
                        
                        return {
                            success: true,
                            oldScrollTop: oldScrollTop,
                            newScrollTop: scrollContainer.scrollTop,
                            scrollHeight: scrollContainer.scrollHeight,
                            element: 'scroll-container'
                        };
                    }
                    
                    // 如果找不到滚动容器，尝试滚动整个页面
                    let oldScrollY = window.scrollY;
                    window.scrollTo(0, document.body.scrollHeight);
                    return {
                        success: false,
                        oldScrollTop: oldScrollY,
                        newScrollTop: window.scrollY,
                        scrollHeight: document.body.scrollHeight,
                        element: 'body'
                    };
                    """
                    scroll_result = self.driver.execute_script(scroll_script)
                    
                    # 记录滚动结果
                    if scroll_result['success']:
                        logger.info(f"使用评论列表容器滚动 - 从 {scroll_result['oldScrollTop']} 到 {scroll_result['newScrollTop']}")
                        if scroll_result['oldScrollTop'] == scroll_result['newScrollTop']:
                            logger.warning("滚动位置未改变，可能已到底部")
                    else:
                        logger.info(f"使用页面全局滚动 - 从 {scroll_result['oldScrollTop']} 到 {scroll_result['newScrollTop']}")
                    
                except Exception as e:
                    logger.warning(f"滚动失败: {str(e)}")
                    # 如果JavaScript执行失败，使用selenium的方式滚动
                    try:
                        # 找到最后一条评论并滚动到它
                        comments = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'comment-item')]")
                        if comments:
                            last_comment = comments[-1]
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", last_comment)
                            logger.info("使用scrollIntoView滚动到最后一条评论")
                    except:
                        # 最后的备选方案：滚动整个页面
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        logger.info("使用页面全局滚动（备选方案）")
                
                # 等待新评论加载
                self.random_sleep(2, 3)
                
                # 检查是否有新评论加载
                new_comments = len(self.driver.find_elements(By.XPATH, "//div[@data-e2e='comment-list']//div[@data-e2e='comment-item']"))
                
                if new_comments <= current_comments:
                    no_new_data_count += 1
                    logger.info(f"未检测到新评论，连续 {no_new_data_count}/5 次")
                else:
                    no_new_data_count = 0
                    logger.info(f"检测到 {new_comments - current_comments} 条新评论")
                    
                    # 处理新加载的评论用户
                    comment_elements = self.driver.find_elements(By.XPATH, "//div[@data-e2e='comment-list']//div[@data-e2e='comment-item']")
                    
                    if not comment_elements:
                        logger.warning("未找到评论元素")
                        continue
                    
                    # 只处理新加载的评论
                    for comment_element in comment_elements[current_comments:new_comments]:
                        try:
                            # 提取用户链接和ID
                            user_link = comment_element.find_element(By.XPATH, ".//a[contains(@href, '/user/')]")
                            if not user_link:
                                continue
                                
                            user_href = user_link.get_attribute("href")
                            if not user_href or "/user/" not in user_href:
                                continue
                                
                            user_id = user_href.split("/user/")[1].split("?")[0]
                            if not user_id:
                                continue
                            
                            # 获取用户名
                            username = user_link.text.strip() or "未知用户"
                            
                            # 验证用户信息并添加到数据库
                            if user_id not in processed_users:
                                if self.db.is_followed(user_id):
                                    logger.info(f"用户 {user_id} ({username}) 已在关注列表中，跳过")
                                    processed_users.add(user_id)
                                    continue
                                
                                processed_users.add(user_id)
                                
                                if self.db.add_follow_fan(user_id, username, "video_comment", video_url):
                                    extracted_users += 1
                                    logger.info(f"已提取评论用户 {extracted_users}/{max_extract}: {username} ({user_id})")
                                    if extracted_users >= max_extract:
                                        break
                                
                        except Exception as e:
                            logger.warning(f"处理评论用户失败: {str(e)}")
                            continue
                
                scroll_count += 1
                
                if extracted_users >= max_extract:
                    break
                
                if no_new_data_count >= 5:
                    logger.info("连续5次未检测到新评论，认为已到达底部")
                    break
            
            logger.info(f"成功从视频 {video_url} 中提取 {extracted_users} 个评论用户")
            
            # 4. 发送评论
            if extracted_users >= min_extract_users:
                if self._post_comment(video_url):
                    logger.info(f"已达到最小提取用户数 {min_extract_users}，标记视频为已处理")
                    self.db.mark_video_processed(video_url, True)
                    return True
                else:
                    logger.warning("评论发送失败，但已提取足够用户")
                    return True
            else:
                logger.warning(f"提取的用户数 {extracted_users} 小于最小要求 {min_extract_users}，视频将不会被标记为已处理")
                return False
            
        except Exception as e:
            logger.error(f"评论视频并提取用户失败: {str(e)}")
            save_screenshot(self.driver, "video_comment_error")
            return False
    
    def _post_comment(self, video_url):
        """发送评论"""
        try:
            comment_text = "新人涨粉，互关必回"
            
            # 查找评论输入框
            try:
                comment_container = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "comment-input-inner-container"))
                )
                
                comment_container.click()
                self.random_sleep(1, 2)
                
                editor = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "public-DraftEditor-content"))
                )
                
                editor.clear()
                self.random_sleep(0.5, 1)
                
                for char in comment_text:
                    editor.send_keys(char)
                    self.random_sleep(0.1, 0.3)
                
                logger.info("找到评论输入框并输入内容")
                self.random_sleep(1, 2)
            except Exception as e:
                logger.error(f"未找到评论输入框或输入失败: {str(e)}")
                return False
            
            # 发送评论
            try:
                send_button = self.wait.until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "NUzvFSPe"))
                )
                
                self.driver.execute_script("arguments[0].click();", send_button)
                logger.info("点击发送按钮")
                self.random_sleep(2, 3)
                
                try:
                    self.wait.until_not(
                        EC.presence_of_element_located((By.CLASS_NAME, "NUzvFSPe"))
                    )
                    logger.info("评论发送成功")
                    return True
                except:
                    logger.warning("评论发送状态未知，可能需要人工验证")
                    save_screenshot(self.driver, "comment_send_status")
                    
                    user_input = input("请检查评论是否发送成功，如果需要验证码请完成验证。是否继续？(y/n): ")
                    return user_input.lower() == 'y'
                
            except Exception as e:
                logger.warning(f"发送评论遇到异常: {str(e)}")
                save_screenshot(self.driver, "send_comment_error")
                return False
                
        except Exception as e:
            logger.error(f"发送评论失败: {str(e)}")
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