"""
浏览器管理模块

该模块提供了浏览器初始化、配置和会话管理的功能。
"""

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    ElementClickInterceptedException,
    StaleElementReferenceException,
    NoSuchElementException
)
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import os
import time
import random
from datetime import datetime
from .logger import logger, save_screenshot, save_html
from .selectors import COMMON

class BrowserManager:
    """浏览器管理类，负责浏览器的初始化、配置和会话管理"""
    
    def __init__(self, config, db):
        """
        初始化浏览器管理器
        
        参数:
            config: 配置对象
            db: 数据库对象
        """
        self.config = config
        self.db = db
        self.driver = None
        self.wait = None
        self.retry_count = 3
        
    def start(self):
        """启动Edge浏览器并初始化WebDriver"""
        try:
            # 使用Selenium 4的原生Edge支持
            service = Service(EdgeChromiumDriverManager().install())
            options = webdriver.EdgeOptions()
            
            # 设置用户数据目录，保存登录状态
            user_data_dir = os.path.join(os.getcwd(), 'browser_data')
            os.makedirs(user_data_dir, exist_ok=True)
            options.add_argument(f"--user-data-dir={user_data_dir}")
            
            # 使用已安装的Web应用模式
            options.add_argument("--app=https://www.douyin.com")
            # 忽略SSL错误
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--ignore-ssl-errors")
            options.add_argument("--allow-insecure-localhost")
            # 禁用不必要的连接和下载
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-component-update")
            options.add_argument("--disable-domain-reliability")
            options.add_argument("--disable-sync")
            # 禁用日志
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            
            self.driver = webdriver.Edge(service=service, options=options)
            self.wait = WebDriverWait(self.driver, 10)
            
            # 检查是否已登录
            logger.info("正在检查登录状态...")
            self.driver.get("https://www.douyin.com")
            
            # 等待页面加载完成
            time.sleep(5)  # 给页面足够的加载时间
            
            try:
                # 尝试验证登录状态
                if self.verify_login():
                    logger.info("检测到已登录状态！")
                else:
                    # 如果未检测到登录状态，提示用户登录
                    logger.info("未检测到登录状态，请在浏览器中手动登录抖音...")
                    input("登录完成后按回车键继续...")
                    
                    # 再次验证登录状态
                    if not self.verify_login():
                        raise Exception("登录验证失败，请确保已正确登录")
            except Exception as e:
                logger.info(f"登录状态检查失败: {str(e)}")
                logger.info("请在浏览器中手动登录抖音...")
                input("登录完成后按回车键继续...")
                
                # 最后一次验证登录状态
                self.verify_login()
                
            logger.info("登录成功！")
            return self.driver, self.wait
            
        except Exception as e:
            logger.error(f"启动失败: {str(e)}")
            raise
            
    def verify_login(self):
        """验证是否已登录"""
        try:
            # 尝试检查多个可能的登录状态指示元素
            for selector in COMMON['LOGIN_CHECK']:
                try:
                    self.driver.find_element(By.XPATH, selector)
                    logger.info(f"检测到登录状态指示元素: {selector}")
                    return True
                except NoSuchElementException:
                    continue
                    
            # 如果所有选择器都没有找到匹配元素，则认为未登录
            raise Exception("未检测到任何登录状态指示元素")
            
        except Exception as e:
            logger.error(f"登录验证失败: {str(e)}")
            raise Exception("登录验证失败，请确保已正确登录")
    
    def is_working_hour(self):
        """
        检查当前是否在工作时间范围内
        
        如果配置了全天运行（working_hours为空列表或包含[0, 24]），则始终返回True
        否则检查当前时间是否在任一工作时间范围内
        """
        # 检查是否配置了全天运行
        if not self.config['working_hours'] or [0, 24] in self.config['working_hours']:
            logger.info("已配置全天运行模式")
            return True
            
        # 检查当前时间是否在工作时间范围内
        current_hour = datetime.now().hour
        for start, end in self.config['working_hours']:
            if start <= current_hour < end:
                logger.info(f"当前时间 {current_hour}:00 在工作时间范围 {start}:00-{end}:00 内")
                return True
                
        logger.info(f"当前时间 {current_hour}:00 不在任何工作时间范围内")
        return False
        
    def random_sleep(self, min_time, max_time):
        """随机等待一段时间"""
        time.sleep(random.uniform(min_time, max_time))
        
    def retry_on_exception(self, func, *args, **kwargs):
        """带重试机制的函数执行器"""
        for i in range(self.retry_count):
            try:
                return func(*args, **kwargs)
            except (TimeoutException, ElementClickInterceptedException, 
                    StaleElementReferenceException) as e:
                if i == self.retry_count - 1:
                    raise
                logger.warning(f"操作失败，正在重试 ({i+1}/{self.retry_count}): {str(e)}")
                self.random_sleep(1, 2)
        return False
        
    def stop(self):
        """停止程序并清理资源"""
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")
            
    def quit(self):
        """停止程序并清理资源（stop方法的别名）"""
        self.stop()

    def is_browser_closed(self):
        """
        检查浏览器是否已关闭
        
        返回:
            如果浏览器已关闭返回True，否则返回False
        """
        try:
            # 检查窗口句柄
            if self.driver and self.driver.window_handles:
                window_handle = self.driver.window_handles[0]
                logger.info(f"通过窗口句柄检测：浏览器窗口正常，句柄: {window_handle}")
                
                # 执行JavaScript检查
                user_agent = self.driver.execute_script("return navigator.userAgent;")
                logger.info(f"通过JavaScript执行检测：浏览器窗口正常，UserAgent: {user_agent[:50]}...")
                
                return False
        except Exception as e:
            logger.warning(f"浏览器检测失败，可能已关闭: {str(e)}")
            return True
        
        return True
    
    def is_browser_alive(self):
        """
        检查浏览器会话是否有效
        
        返回:
            如果浏览器会话有效返回True，否则返回False
        """
        try:
            # 尝试执行一个简单的JavaScript命令来检查会话是否有效
            self.driver.execute_script("return 1;")
            return True
        except Exception as e:
            # 检查是否是会话失效错误
            if any(error_msg in str(e) for error_msg in ["invalid session id", "no such session", "browser has closed"]):
                logger.error(f"浏览器会话已失效: {str(e)}")
                return False
            # 其他错误可能是临时的，仍然认为浏览器有效
            logger.warning(f"浏览器检查出现错误，但可能仍然有效: {str(e)}")
            return True
    
    def restart_browser(self):
        """
        重启浏览器
        
        返回:
            重启成功返回True，否则返回False
        """
        logger.info("尝试重启浏览器...")
        
        try:
            # 先尝试关闭现有浏览器
            self.stop()
            
            # 等待一段时间确保浏览器完全关闭
            time.sleep(5)
            
            # 重新启动浏览器
            result = self.start()
            
            if result:
                logger.info("浏览器重启成功")
                return True
            else:
                logger.error("浏览器重启失败")
                return False
                
        except Exception as e:
            logger.error(f"重启浏览器时出错: {str(e)}")
            return False
    
    def check_and_restart_browser(self):
        """
        检查浏览器状态，如果异常则尝试重启
        
        返回:
            浏览器状态正常或重启成功返回True，否则返回False
        """
        logger.info("检查浏览器状态...")
        
        # 检查浏览器是否已关闭
        if self.is_browser_closed():
            logger.warning("浏览器已关闭，尝试重启")
            return self.restart_browser()
        
        # 检查浏览器会话是否有效
        if not self.is_browser_alive():
            logger.warning("浏览器会话已失效，尝试重启")
            return self.restart_browser()
        
        # 检查浏览器连接状态
        try:
            current_url = self.driver.current_url
            logger.info(f"浏览器连接正常，当前URL: {current_url}")
        except Exception as e:
            logger.warning(f"浏览器连接异常: {str(e)}")
            return self.restart_browser()
        
        # 检查登录状态
        if not self.check_login_status():
            logger.warning("登录状态异常，尝试重新登录")
            
            # 尝试重新登录
            try:
                self.driver.get("https://www.douyin.com/")
                time.sleep(3)
                
                if self.check_login_status():
                    logger.info("重新登录成功")
                else:
                    logger.warning("重新登录失败，尝试重启浏览器")
                    return self.restart_browser()
            except Exception as e:
                logger.warning(f"尝试重新登录时出错: {str(e)}")
                return self.restart_browser()
        
        logger.info("浏览器状态正常，登录有效")
        return True
    
    def check_login_status(self):
        """
        检查当前登录状态
        
        返回:
            登录有效返回True，无效返回False
        """
        try:
            if self.driver is None:
                logger.warning("浏览器未初始化，无法检查登录状态")
                return False
            
            # 访问抖音首页
            try:
                current_url = self.driver.current_url
                if "douyin.com" not in current_url:
                    logger.info("当前不是抖音页面，导航到抖音首页")
                    self.driver.get("https://www.douyin.com")
                    logger.info("通过URL访问抖音首页: https://www.douyin.com")
                    time.sleep(3)  # 等待页面加载
            except Exception as e:
                logger.warning(f"访问抖音首页失败: {str(e)}")
                return False
            
            # 检查是否被重定向到登录页
            current_url = self.driver.current_url
            if "login" in current_url:
                logger.warning(f"通过URL检测到页面被重定向到登录页: {current_url}，登录状态无效")
                return False
            
            # 检查登录状态指示元素
            try:
                for selector in COMMON['LOGIN_CHECK']:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        logger.info(f"通过元素选择器检测到登录状态指示元素: {selector}")
                        return True
                    except NoSuchElementException:
                        continue
            except Exception as e:
                logger.warning(f"检查登录状态指示元素时出错: {str(e)}")
            
            # 尝试访问个人主页，进一步验证登录状态
            try:
                # 直接访问个人主页
                logger.info("尝试直接访问个人主页")
                self.driver.get("https://www.douyin.com/user/self")
                logger.info("通过URL访问个人主页: https://www.douyin.com/user/self")
                time.sleep(3)  # 等待页面加载
                
                # 检查当前URL是否包含user
                current_url = self.driver.current_url
                if "user" in current_url and "login" not in current_url:
                    logger.info(f"通过URL检测到成功访问个人主页: {current_url}")
                    
                    # 使用更多选择器检查个人信息元素
                    profile_selectors = COMMON['PROFILE_INFO'] + [
                        "//div[contains(@class, 'author')]",
                        "//div[contains(@class, 'profile')]",
                        "//div[contains(@class, 'nickname')]",
                        "//div[contains(@class, 'avatar')]",
                        "//div[contains(@class, 'follow-info')]",
                        "//span[contains(text(), '粉丝') or contains(text(), '关注')]",
                        "//div[contains(@data-e2e, 'user-info')]"
                    ]
                    
                    for selector in profile_selectors:
                        try:
                            element = self.driver.find_element(By.XPATH, selector)
                            logger.info(f"通过元素选择器检测到个人主页信息元素: {selector}")
                            return True
                        except NoSuchElementException:
                            continue
                    
                    # 使用JavaScript检测页面内容
                    try:
                        # 检查页面是否包含个人信息相关文本
                        js_result = self.driver.execute_script("""
                            var pageText = document.body.innerText;
                            if (pageText.includes('粉丝') || pageText.includes('关注') || 
                                pageText.includes('获赞') || pageText.includes('作品')) {
                                return true;
                            }
                            
                            // 检查是否有个人信息相关元素
                            var profileElements = document.querySelectorAll('div[class*="profile"], div[class*="author"], div[class*="user"]');
                            return profileElements.length > 0;
                        """)
                        
                        if js_result:
                            logger.info("通过JavaScript检测到个人主页信息元素")
                            return True
                    except Exception as e:
                        logger.warning(f"使用JavaScript检测个人主页信息时出错: {str(e)}")
                    
                    # 如果URL正确但未找到个人信息元素，可能是页面结构变化，但仍然认为登录有效
                    logger.info("URL显示在个人主页，但未找到预期的个人信息元素，仍然认为登录有效")
                    return True
                else:
                    logger.warning(f"通过URL检测到未能成功访问个人主页，当前URL: {current_url}")
            except Exception as e:
                logger.warning(f"访问个人主页验证登录状态时出错: {str(e)}")
            
            # 尝试使用JavaScript检测登录状态
            try:
                js_result = self.driver.execute_script("""
                    // 检查是否有登录相关的cookie
                    var hasCookie = document.cookie.includes('sessionid') || document.cookie.includes('passport_csrf_token');
                    
                    // 检查页面上是否有登录用户相关的元素
                    var hasLoginElements = false;
                    var elements = document.querySelectorAll('div, span, a');
                    for (var i = 0; i < elements.length; i++) {
                        var el = elements[i];
                        if ((el.className && (el.className.includes('avatar') || el.className.includes('user') || 
                             el.className.includes('login') || el.className.includes('profile'))) ||
                            (el.innerText && (el.innerText.includes('我的') || el.innerText.includes('个人中心')))) {
                            hasLoginElements = true;
                            break;
                        }
                    }
                    
                    return hasCookie || hasLoginElements;
                """)
                
                if js_result:
                    logger.info("通过JavaScript检测到登录状态有效")
                    return True
            except Exception as e:
                logger.warning(f"使用JavaScript检测登录状态时出错: {str(e)}")
            
            # 如果所有检查都未能确认登录状态，则认为登录无效
            logger.warning("无法确认登录状态，可能已失效")
            return False
            
        except Exception as e:
            logger.error(f"检查登录状态时出错: {str(e)}")
            return False 