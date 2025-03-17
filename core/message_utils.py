"""
私信工具模块

该模块提供了发送私信的共通功能。
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import random
import time
from .logger import logger, save_screenshot

class MessageUtils:
    """私信工具类，提供发送私信的共通方法"""
    
    def __init__(self, driver, wait, random_sleep, db):
        """
        初始化私信工具类
        
        参数:
            driver: WebDriver对象
            wait: WebDriverWait对象
            random_sleep: 随机等待函数
            db: 数据库对象
        """
        self.driver = driver
        self.wait = wait
        self.random_sleep = random_sleep
        self.db = db
        self.send_msg_limit=False

    def check_message_sent(self, message: str) -> bool:
        """
        检查消息是否发送成功
        
        参数:
            message: 要检查的消息内容
            
        返回:
            bool: 消息是否发送成功
        """
        try:
            # 获取消息预览文本(用于日志)
            message_preview = message[:20] if len(message) > 20 else message
            message_found = False
            
            # 尝试多次检查消息是否出现
            max_retries = 3
            for retry in range(max_retries):
                logger.info(f"第 {retry + 1} 次检查消息是否发送成功...")
                retry_start_time = time.time()
                
                try:
                    # 获取messageContent元素
                    message_content = self.driver.find_element(By.ID, "messageContent")
                    if not message_content:
                        logger.warning("未找到messageContent元素")
                        continue
                        
                    # 获取所有pre标签中的文本内容
                    pre_elements = message_content.find_elements(By.TAG_NAME, "pre")
                    if not pre_elements:
                        logger.warning("未找到消息内容元素")
                        continue
                        
                    # 检查每个pre标签中的文本
                    for pre in pre_elements:
                        content = pre.text
                        if not content:
                            continue
                        
                        # 检查div和span标签中的文本
                        reject_send_msg_element = self.driver.find_elements(By.XPATH, "//div[contains(text(), '达到今日上限')]")
                        
                        if reject_send_msg_element:
                            error_text = reject_send_msg_element[0].text
                            self.check_send_msg_limit(True)
                            logger.warning(f"检测到发送失败提示(已达到今日发信上限): {error_text}")
                            return False

                        # 检查div和span标签中的文本
                        error_elements = self.driver.find_elements(By.XPATH, "//div[contains(text(), '发送失败') or contains(text(), '请求频繁') or contains(text(), '操作太频繁') or contains(text(), '稍后再试')] | //span[contains(text(), '发送失败') or contains(text(), '请求频繁') or contains(text(), '操作太频繁') or contains(text(), '稍后再试')]")
                        
                        if error_elements:
                            error_text = error_elements[0].text
                            logger.warning(f"检测到发送失败提示: {error_text}")
                            return False
                            
                        # 检查消息是否在文本内容中
                        if message in content:
                            message_found = True
                            logger.info(f"在聊天窗口中找到发送的消息内容: {message_preview}...")
                            break
                            
              
                    if message_found:
                        break
                    
                except Exception as e:
                    logger.debug(f"获取消息内容失败: {str(e)}")
                    continue
                
                if message_found:
                    logger.info(f"消息发送成功确认，本次检查耗时: {time.time() - retry_start_time:.2f}秒")
                    break
                    
                if retry < max_retries - 1:
                    wait_time = random.uniform(3, 5)
                    logger.info(f"未找到消息内容，等待 {wait_time:.2f} 秒后进行第 {retry + 2} 次检查...")
                    time.sleep(wait_time)
                
            return message_found
            
        except Exception as e:
            logger.error(f"检查消息发送状态时出错: {str(e)}")
            return False

    def send_message(self, user_id: str, username: str, message: str, days_since_follow: int = None, should_record: bool = True) -> bool:
        """
        发送私信给指定用户
        
        参数:
            user_id: 用户ID
            username: 用户名
            message: 要发送的消息内容
            days_since_follow: 粉丝关注天数（可选）
            should_record: 是否记录到数据库（默认True）
            
        返回:
            bool: 是否成功发送
        """
        try:
            if self.check_send_msg_limit():
                logger.warning(f"自动检测到今日私信已上限，私信功能关闭: {username} ({user_id})")
                return False

            # 访问用户主页
            logger.info(f"访问用户主页准备发送私信: {username} ({user_id})")
            self.driver.get(f"https://www.douyin.com/user/{user_id}")
            wait_time = random.uniform(3, 5)
            logger.info(f"随机等待时长: {wait_time:.2f}秒")
            self.random_sleep(3, 5)
            
            # 查找私信按钮
            message_button = None
            message_button_selectors = [
                # 最宽松的选择器，仅基于按钮内容
                "//button//span[text()='私信']/parent::button"
            ]
            
            for selector in message_button_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        # 检查按钮是否可见且可点击
                        if element.is_displayed() and element.is_enabled():
                            message_button = element
                            logger.info(f"找到可用的私信按钮: {selector}")
                            break
                    if message_button:
                        break
                except Exception as e:
                    continue
            
            if not message_button:
                logger.warning(f"未找到私信按钮: {username} ({user_id})")
                save_screenshot(self.driver, f"no_message_button_{user_id}")
                return False
            
            # 点击私信按钮
            logger.info(f"尝试点击私信按钮: {username} ({user_id})")
            click_success = False
            
            # 尝试多种点击方法
            click_methods = [
                # 方法1: 直接点击
                lambda: message_button.click(),
                
                # 方法2: 使用JavaScript点击
                lambda: self.driver.execute_script("arguments[0].click();", message_button),
                
                # 方法3: 使用ActionChains点击
                lambda: ActionChains(self.driver).move_to_element(message_button).click().perform(),
                
                # 方法4: 先移动到元素，等待后再点击
                lambda: (ActionChains(self.driver).move_to_element(message_button).perform(), 
                        time.sleep(1), 
                        message_button.click()),
                
                # 方法5: 使用JavaScript滚动到元素后点击
                lambda: (self.driver.execute_script("arguments[0].scrollIntoView(true);", message_button),
                        time.sleep(1),
                        message_button.click())
            ]
            
            for i, click_method in enumerate(click_methods, 1):
                try:
                    click_method()
                    wait_time = random.uniform(2, 3)
                    logger.info(f"点击私信按钮后随机等待时长: {wait_time:.2f}秒")
                    self.random_sleep(2, 3)
                    # 验证点击是否成功（检查私信对话框是否出现）
                    if len(self.driver.find_elements(By.XPATH, "//div[contains(@class, 'im-richtext-container')]")) > 0:
                        click_success = True
                        logger.info(f"成功点击私信按钮（方法{i}）")
                        break
                except Exception as e:
                    logger.warning(f"点击方法{i}失败: {str(e)}")
                    continue
            
            if not click_success:
                logger.error(f"所有点击方法都失败了: {username} ({user_id})")
                save_screenshot(self.driver, f"click_message_button_failed_{user_id}")
                return False
            
            # 查找私信输入框
            message_input = None
            message_input_selectors = [
                "//div[contains(@class, 'public-DraftEditor-content')]",
                "//div[contains(@class, 'DraftEditor-editorContainer')]//div[@contenteditable='true']",
                "//div[contains(@class, 'im-richtext-container')]//div[@contenteditable='true']"
            ]
            
            # 增加重试次数
            max_input_retries = 3
            for input_retry in range(max_input_retries):
                try:
                    # 等待私信对话框完全加载
                    wait_time = random.uniform(2, 3)
                    logger.info(f"等待私信对话框加载, 等待时长: {wait_time:.2f}秒")
                    time.sleep(wait_time)
                    
                    # 尝试查找输入框
                    for selector in message_input_selectors:
                        try:
                            # 使用显式等待
                            message_input = self.wait.until(
                                EC.presence_of_element_located((By.XPATH, selector))
                            )
                            if message_input and message_input.is_displayed() and message_input.is_enabled():
                                logger.info(f"找到可用的私信输入框: {selector}")
                                break
                        except:
                            continue
                        
                    if message_input:
                        break
                    
                    logger.warning(f"第 {input_retry + 1} 次尝试未找到可用的私信输入框")
                    
                except Exception as e:
                    logger.warning(f"第 {input_retry + 1} 次查找私信输入框失败: {str(e)}")
                    if input_retry < max_input_retries - 1:
                        continue
            
            if not message_input:
                logger.warning(f"未找到私信输入框: {username} ({user_id})")
                return False
                
            # 输入私信内容
            logger.info(f"输入私信内容: {message}")
            try:
                # 先点击输入框激活它
                try:
                    # 使用JavaScript点击
                    self.driver.execute_script("arguments[0].click();", message_input)
                except:
                    # 如果JavaScript点击失败,尝试普通点击
                    message_input.click()
                
                wait_time = random.uniform(1, 2)
                logger.info(f"点击输入框后随机等待时长: {wait_time:.2f}秒")
                self.random_sleep(1, 2)
                
                # 清空输入框
                try:
                    message_input.clear()
                except:
                    # 如果普通清空失败,使用Ctrl+A和Delete键
                    message_input.send_keys(Keys.CONTROL + "a")
                    message_input.send_keys(Keys.DELETE)
                
                wait_time = random.uniform(0.5, 1)
                logger.info(f"清空输入框后随机等待时长: {wait_time:.2f}秒")
                self.random_sleep(0.5, 1)
                
                # 模拟人工输入
                for char in message:
                    message_input.send_keys(char)
                    # 随机等待一个很短的时间，模拟人工输入速度
                    char_wait_time = random.uniform(0.1, 0.3)
                    time.sleep(char_wait_time)
                
                wait_time = random.uniform(1, 2)
                logger.info(f"输入完成后随机等待时长: {wait_time:.2f}秒")
                self.random_sleep(1, 2)
                
            except Exception as e:
                logger.error(f"输入私信内容失败: {str(e)}")
                return False
                
            # 查找发送按钮
            send_button = None
            send_button_selectors = [
                # 使用e2e-send-msg-btn功能类名
                "//span[contains(@class, 'e2e-send-msg-btn')]"
            ]
            
            # 先点击输入框以激活发送按钮
            try:
                logger.info("尝试点击输入框以激活发送按钮...")
                message_input.click()
                wait_time = random.uniform(1, 2)
                logger.info(f"点击输入框后等待: {wait_time:.2f}秒")
                time.sleep(wait_time)
            except Exception as e:
                logger.warning(f"点击输入框失败: {str(e)}")
            
            for selector in send_button_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            send_button = element
                            logger.info(f"找到可用的发送按钮: {selector}")
                            break
                    if send_button:
                        break
                except Exception as e:
                    continue
            
            if send_button:
                # 点击发送按钮
                logger.info("开始点击发送按钮")
                start_time = time.time()
                try:
                    # 直接点击发送按钮
                    send_button.click()
                    click_time = time.time()
                    logger.info(f"发送按钮点击完成，耗时: {click_time - start_time:.2f}秒")
                    
                    wait_time = random.uniform(5, 8)
                    logger.info(f"开始等待消息发送完成，计划等待时长: {wait_time:.2f}秒")
                    time.sleep(wait_time)
                    
                    actual_wait_time = time.time() - click_time
                    logger.info(f"消息发送等待完成，实际等待时长: {actual_wait_time:.2f}秒")
                    
                    # 检查消息是否发送成功
                    if self.check_message_sent(message):
                        total_time = time.time() - start_time
                        logger.info(f"消息发送全流程完成，总耗时: {total_time:.2f}秒")
                        if should_record:
                            self.db.add_message_record(user_id, message)
                        return True
                    else:
                        logger.warning(f"发送私信失败,标记用户 {username} ({user_id}) 今天不再发送私信")
                        if days_since_follow is not None and should_record:
                            self.db.mark_user_message_failed(user_id, days_since_follow + 1)
                        return False
                    
                except Exception as e:
                    logger.error(f"发送消息过程出错，耗时: {time.time() - start_time:.2f}秒，错误: {str(e)}")
                    return False
            else:
                # 如果没有找到发送按钮，尝试按回车键发送
                logger.info("未找到发送按钮，尝试按回车键发送")
                message_input.send_keys(Keys.ENTER)
                wait_time = random.uniform(2, 3)
                logger.info(f"按回车键发送后随机等待时长: {wait_time:.2f}秒")
                self.random_sleep(2, 3)
            
                # 使用相同的检查逻辑
                if self.check_message_sent(message):
                    logger.info(f"成功发送私信给用户: {username} ({user_id})")
                    if should_record:
                        self.db.add_message_record(user_id, message)
                    return True
                else:
                    logger.warning(f"发送私信失败,标记用户 {username} ({user_id}) 今天不再发送私信")
                    if days_since_follow is not None and should_record:
                        self.db.mark_user_message_failed(user_id, days_since_follow + 1)
                    return False
                
        except Exception as e:
            logger.error(f"发送私信失败: {str(e)}")
            save_screenshot(self.driver, f"send_message_error_{user_id}")
            return False 
    """
    方法概述：自动检测是否送信上限
    """
    def check_send_msg_limit(self, *arg):
        if len(arg) > 0:
            self.send_msg_limit = True
        return self.send_msg_limit