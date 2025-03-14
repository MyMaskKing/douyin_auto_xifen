"""
私信管理模块

该模块提供了对粉丝进行私信互动的功能。
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import random
import time
from datetime import datetime, timedelta
from .logger import logger, save_screenshot
from utils.db import Database
from utils.config import load_config
from .browser import BrowserManager
from selenium.webdriver.common.action_chains import ActionChains

class MessageManager:
    """私信管理器，负责处理粉丝私信互动"""
    
    def __init__(self, browser_manager: BrowserManager, db: Database, config: dict):
        """
        初始化私信管理器
        
        参数:
            browser_manager: 浏览器管理器对象
            db: 数据库对象
            config: 配置对象
        """
        self.browser = browser_manager
        self.db = db
        self.config = config
        self.driver = browser_manager.driver
        self.wait = browser_manager.wait
        self.random_sleep = browser_manager.random_sleep
        
        # 每日最大私信数量
        self.max_messages_per_day = config.get('operation', {}).get('fan_list_tasks', {}).get('max_messages_per_day', 100)
        
        # 每轮处理的粉丝数量
        self.batch_size = config.get('operation', {}).get('fan_list_tasks', {}).get('batch_size', 50)
        
        # 私信模板
        self.message_templates = {
            0: config.get('message_templates', {}).get('day_1', [
                "你好呀，很高兴认识你~",
                "Hi，我是{username}，谢谢你的关注！",
                "嗨，感谢关注，希望我们能成为好朋友~"
            ]),
            1: config.get('message_templates', {}).get('day_2', [
                "最近在忙什么呢？",
                "今天过得怎么样呀？",
                "有什么有趣的事情想分享吗？"
            ]),
            2: config.get('message_templates', {}).get('day_3', [
                "这几天聊得很开心，希望以后也能经常互动~",
                "感谢这几天的交流，你真的很有趣！",
                "和你聊天很愉快，期待更多的分享~"
            ])
        }

    def get_message_template(self, days_since_follow: int, username: str) -> str:
        """
        获取指定天数的消息模板
        
        参数:
            days_since_follow: 粉丝关注天数（0,1,2分别代表第一、二、三天）
            username: 用户名，用于替换模板中的变量
            
        返回:
            str: 消息模板内容，如果没有找到合适的模板则返回None
        """
        try:
            # 验证days_since_follow的值
            if not isinstance(days_since_follow, int) or days_since_follow not in [0, 1, 2]:
                logger.warning(f"无效的days_since_follow值: {days_since_follow}")
                return None
                
            # 获取消息模板配置
            message_templates = self.config.get('message_templates', {})
            if not message_templates:
                logger.error("配置文件中未找到消息模板")
                return None
                
            # 获取对应天数的模板列表
            template_key = f"day_{days_since_follow + 1}"  # 转换为day_1, day_2, day_3
            templates = message_templates.get(template_key, [])
            
            if not templates:
                logger.warning(f"未找到第 {days_since_follow + 1} 天的消息模板")
                return None
                
            # 随机选择一个模板
            message_template = random.choice(templates)
            
            # 返回格式化后的消息
            return message_template.format(username=username)
            
        except Exception as e:
            logger.error(f"获取消息模板失败: {str(e)}")
            return None
    
    def send_message(self, user_id: str, username: str, days_since_follow: int) -> bool:
        """
        发送私信给指定用户
        
        参数:
            user_id: 用户ID
            username: 用户名
            days_since_follow: 粉丝关注天数（0,1,2分别代表第一、二、三天）
            
        返回:
            bool: 是否成功发送
        """
        try:
            # 获取对应天数的消息模板
            message = self.get_message_template(days_since_follow, username)
            if not message:
                logger.error(f"无法获取第 {days_since_follow + 1} 天的消息模板")
                return False
                
            # 访问用户主页
            logger.info(f"访问用户主页准备发送私信: {username} ({user_id})")
            self.driver.get(f"https://www.douyin.com/user/{user_id}")
            wait_time = random.uniform(3, 5)
            logger.info(f"随机等待时长: {wait_time:.2f}秒")
            self.random_sleep(3, 5)
            
            # 保存页面截图
            # save_screenshot(self.driver, f"send_message_{user_id}", level="NORMAL")
            
            # 查找私信按钮
            message_button = None
            message_button_selectors = [
                # 最精确的选择器，基于完整的类名组合
                "//div[contains(@class, 'XB2sFwjg')]//button[contains(@class, 'semi-button-secondary') and contains(@class, 'K8kpIsJm')]//span[text()='私信']/parent::button",
                
                # 基于父div和类名组合的选择器
                "//div[contains(@class, 'XB2sFwjg')]//button[contains(@class, 'K8kpIsJm')]//span[text()='私信']/parent::button",
                
                # 基于特定类名组合的选择器
                "//button[contains(@class, 'semi-button-secondary') and contains(@class, 'K8kpIsJm')]//span[text()='私信']/parent::button",
                
                # 基于按钮内容和类名的选择器
                "//button[contains(@class, 'K8kpIsJm')]//span[text()='私信']/parent::button",
                
                # 基于semi-button类和内容的选择器
                "//button[contains(@class, 'semi-button-secondary')]//span[text()='私信']/parent::button",
                
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
                wait_time = random.uniform(1, 2)
                logger.info(f"点击输入框后随机等待时长: {wait_time:.2f}秒")
                self.random_sleep(1, 2)
                
                # 清空输入框
                message_input.clear()
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
                    wait_time = random.uniform(2, 3)
                    logger.info(f"点击发送按钮后随机等待时长: {wait_time:.2f}秒")
                    self.random_sleep(2, 3)
                except:
                    try:
                        # 如果直接点击失败，尝试点击父元素
                        parent = send_button.find_element(By.XPATH, "..")
                        parent.click()
                        wait_time = random.uniform(2, 3)
                        logger.info(f"点击发送按钮父元素后随机等待时长: {wait_time:.2f}秒")
                        self.random_sleep(2, 3)
                    except:
                        # 如果点击父元素也失败，尝试使用JavaScript点击
                        try:
                            self.driver.execute_script("arguments[0].click();", send_button)
                            wait_time = random.uniform(2, 3)
                            logger.info(f"使用JavaScript点击发送按钮后随机等待时长: {wait_time:.2f}秒")
                            self.random_sleep(2, 3)
                        except Exception as e:
                            logger.error(f"点击发送按钮失败: {str(e)}")
                            return False
            else:
                # 如果没有找到发送按钮，尝试按回车键发送
                logger.info("未找到发送按钮，尝试按回车键发送")
                message_input.send_keys(Keys.ENTER)
                wait_time = random.uniform(2, 3)
                logger.info(f"按回车键发送后随机等待时长: {wait_time:.2f}秒")
                self.random_sleep(2, 3)
            
            # 检查是否发送成功
            try:
                # 等待消息内容出现在聊天窗口中
                message_content_selectors = [
                    "//div[@id='messageContent']//div[contains(@class, 'iraLLg20')]//span[contains(@class, 'WCSQFekt')]//pre[contains(text(), '{}')]",
                    "//div[@id='messageContent']//div[contains(@class, 'SWIwJC_8')]//span[contains(@class, 'WCSQFekt')]//pre[contains(text(), '{}')]",
                    "//div[@id='messageContent']//div[contains(@class, 'gdUUraP7')][contains(text(), '{}')]",
                    "//div[contains(@class, 'iraLLg20')]//span[contains(@class, 'WCSQFekt')]//pre[contains(text(), '{}')]",
                    "//div[contains(@class, 'SWIwJC_8')]//span[contains(@class, 'WCSQFekt')]//pre[contains(text(), '{}')]",
                    "//div[contains(@class, 'gdUUraP7')][contains(text(), '{}')]",
                    "//div[contains(@class, 'message-content')]//div[contains(text(), '{}')]",
                    "//div[contains(@class, 'message-item')]//div[contains(text(), '{}')]"
                ]
                
                # 检查消息是否出现在聊天窗口中
                message_found = False
                for selector in message_content_selectors:
                    try:
                        # 使用消息内容的前20个字符进行匹配，避免特殊字符问题
                        message_preview = message[:20] if len(message) > 20 else message
                        formatted_selector = selector.format(message_preview)
                        self.wait.until(EC.presence_of_element_located((By.XPATH, formatted_selector)))
                        message_found = True
                        logger.info(f"在聊天窗口中找到发送的消息内容: {message_preview}...")
                        break
                    except:
                        continue
                
                # 检查是否有发送失败的提示
                failure_indicators = [
                    "//div[@id='messageContent']//div[contains(@class, 'kuMUXQBL')]//span[contains(@class, 'uM5tWLIj')][contains(text(), '发送失败')]",
                    "//div[contains(@class, 'kuMUXQBL')]//span[contains(@class, 'uM5tWLIj')][contains(text(), '发送失败')]",
                    "//div[@id='messageContent']//div[contains(text(), '发送失败')]",
                    "//div[@id='messageContent']//div[contains(text(), '请求频繁')]",
                    "//div[@id='messageContent']//div[contains(text(), '操作太频繁')]",
                    "//div[@id='messageContent']//div[contains(text(), '稍后再试')]",
                    "//div[contains(text(), '发送失败')]",
                    "//div[contains(text(), '请求频繁')]",
                    "//div[contains(text(), '操作太频繁')]",
                    "//div[contains(text(), '稍后再试')]",
                    "//div[contains(@class, 'error-message')]",
                    "//div[contains(@class, 'toast-error')]"
                ]
                
                failure_found = False
                for selector in failure_indicators:
                    if len(self.driver.find_elements(By.XPATH, selector)) > 0:
                        failure_found = True
                        logger.warning(f"检测到发送失败提示: {selector}")
                        break
                
                if message_found and not failure_found:
                    logger.info(f"成功发送私信给用户: {username} ({user_id})")
                    
                    # 记录私信历史
                    self.db.add_message_record(user_id, message)
                    
                    return True
                elif failure_found:
                    # 获取重试等待时间
                    retry_wait_time = self.config.get('operation', {}).get('fan_list_tasks', {}).get('message_retry_wait', 300)  # 默认5分钟
                    
                    logger.warning(f"发送私信失败，等待 {retry_wait_time} 秒后重试...")
                    time.sleep(retry_wait_time)
                    logger.info(f"重试等待完成，已等待 {retry_wait_time} 秒")
                    
                    # 重新尝试发送
                    logger.info(f"重新尝试发送私信给用户: {username} ({user_id})")
                    
                    # 清空输入框并重新输入
                    message_input = self.driver.find_element(By.XPATH, "//div[contains(@class, 'public-DraftEditor-content')]")
                    message_input.clear()
                    wait_time = random.uniform(0.5, 1)
                    logger.info(f"重试时清空输入框后随机等待时长: {wait_time:.2f}秒")
                    self.random_sleep(0.5, 1)
                    
                    # 模拟人工输入
                    for char in message:
                        message_input.send_keys(char)
                        char_wait_time = random.uniform(0.05, 0.15)
                        time.sleep(char_wait_time)
                    
                    wait_time = random.uniform(1, 2)
                    logger.info(f"重试时输入完成后随机等待时长: {wait_time:.2f}秒")
                    self.random_sleep(1, 2)
                    
                    # 再次点击发送按钮
                    send_button = self.driver.find_element(By.XPATH, "//span[contains(@class, 'e2e-send-msg-btn')]")
                    send_button.click()
                    wait_time = random.uniform(2, 3)
                    logger.info(f"重试时点击发送按钮后随机等待时长: {wait_time:.2f}秒")
                    self.random_sleep(2, 3)
                    
                    # 再次检查是否发送成功
                    message_found = False
                    for selector in message_content_selectors:
                        try:
                            message_preview = message[:20] if len(message) > 20 else message
                            formatted_selector = selector.format(message_preview)
                            self.wait.until(EC.presence_of_element_located((By.XPATH, formatted_selector)))
                            message_found = True
                            break
                        except:
                            continue
                    
                    failure_found = False
                    for selector in failure_indicators:
                        if len(self.driver.find_elements(By.XPATH, selector)) > 0:
                            failure_found = True
                            break
                    
                    if message_found and not failure_found:
                        logger.info(f"重试成功，已发送私信给用户: {username} ({user_id})")
                        
                        # 记录私信历史
                        self.db.add_message_record(user_id, message)
                        
                        return True
                    else:
                        logger.error(f"重试失败，标记用户 {username} ({user_id}) 今天不再发送私信")
                        
                        # 标记用户今天不再发送私信，将今天的发信次数延后一天
                        self.db.mark_user_message_failed(user_id, days_since_follow + 1)
                        
                        return False
                
            except Exception as e:
                logger.warning(f"无法确认私信是否发送成功: {str(e)}")
                # 再次检查按钮状态
                try:
                    time.sleep(2)
                    # 如果找到了灰色状态的按钮，说明发送成功
                    if len(self.driver.find_elements(By.XPATH, "//span[contains(@class, 'sCp7KhBv') and contains(@class, 'e2e-send-msg-btn') and not(contains(@class, 'EWT1TDgs'))]")) > 0:
                        logger.info(f"通过按钮状态确认私信发送成功: {username} ({user_id})")
                        
                        # 记录私信历史
                        self.db.add_message_record(user_id, message)
                        
                        return True
                except:
                    pass
                return False
                
        except Exception as e:
            logger.error(f"发送私信失败: {str(e)}")
            save_screenshot(self.driver, f"send_message_error_{user_id}")
            return False
    
    def run_fan_message_task(self) -> bool:
        """
        运行粉丝私信任务
        
        功能：
        1. 检查今日私信数量是否达到上限
        2. 获取需要发送私信的粉丝
        3. 根据关注天数发送不同的私信
        
        返回:
            bool: 任务执行成功返回True，否则返回False
        """
        try:
            logger.info("开始执行粉丝私信任务...")
            
            # 检查今日私信数量是否达到上限
            today_count = self.db.get_today_message_count()
            if today_count >= self.max_messages_per_day:
                logger.info(f"今日私信数量已达上限: {today_count}/{self.max_messages_per_day}")
                return True
                
            # 获取需要发送私信的粉丝
            remaining = self.max_messages_per_day - today_count
            batch_size = min(remaining, self.batch_size)
            fans = self.db.get_fans_need_message(limit=batch_size)
            
            if not fans:
                logger.info("没有需要发送私信的粉丝")
                return True
                
            logger.info(f"开始处理 {len(fans)} 个粉丝的私信任务")
            success_count = 0
            
            for fan in fans:
                try:
                    user_id = fan['user_id']
                    username = fan['username']
                    days_since_follow = fan['days_since_follow']
                    
                    # 发送私信
                    if self.send_message(user_id, username, days_since_follow):
                        success_count += 1
                        # 更新粉丝互动状态
                        self.db.update_fan_interaction(user_id)
                        logger.info(f"完成与粉丝 {username} 的第 {days_since_follow + 1} 天互动")
                    
                    # 随机延迟，避免操作过快
                    time.sleep(random.uniform(2, 5))
                    
                except Exception as e:
                    logger.error(f"处理粉丝 {fan.get('username', 'unknown')} 的互动任务失败: {str(e)}")
                    continue
            
            logger.info(f"完成粉丝私信任务，成功发送 {success_count}/{len(fans)} 条私信")
            return True
            
        except Exception as e:
            logger.error(f"运行粉丝私信任务失败: {str(e)}")
            return False 