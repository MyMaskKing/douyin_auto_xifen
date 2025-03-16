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
from .logger import logger, save_screenshot, save_html
from .selectors import COMMON
from utils.paths import get_browser_data_path, get_workspace_path
import os
import time
import random
from datetime import datetime

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
            # 设置 Edge 驱动程序路径
            try:
                # 使用工作目录下的drivers目录存放驱动
                driver_path = os.path.join(get_workspace_path(), 'drivers')
                os.makedirs(driver_path, exist_ok=True)
                os.environ['WDM_LOCAL'] = '1'  # 使用本地缓存
                os.environ['WDM_PATH'] = driver_path  # 设置下载路径
                
                service = Service(EdgeChromiumDriverManager().install())
            except Exception as e:
                # 如果自动下载失败，尝试使用系统Edge浏览器的驱动
                logger.warning(f"自动下载Edge驱动失败: {str(e)}")
                logger.info("尝试使用系统Edge浏览器的驱动...")
                service = Service("msedgedriver")

            # 配置Edge选项
            options = webdriver.EdgeOptions()
            
            # 设置用户数据目录，保存登录状态
            user_data_dir = get_browser_data_path()
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
            
            # 尝试启动浏览器
            try:
                self.driver = webdriver.Edge(service=service, options=options)
            except Exception as e:
                # 如果启动失败，尝试不使用service参数启动
                logger.warning(f"使用service参数启动失败: {str(e)}")
                logger.info("尝试不使用service参数启动...")
                self.driver = webdriver.Edge(options=options)
            
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
        """验证登录状态"""
        try:
            # 访问抖音首页
            self.driver.get("https://www.douyin.com")
            logger.info("访问抖音首页进行登录检测")
            
            # 等待页面加载
            time.sleep(3)
            
            # 检查是否存在登录按钮（未登录状态的标志）
            try:
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button.semi-button.semi-button-primary")
                if login_button.is_displayed():
                    logger.info("检测到登录按钮，未登录状态")
                    return False
            except NoSuchElementException:
                logger.info("未检测到登录按钮，已登录状态")
                return True
            
            # 如果没有找到登录按钮，认为是已登录状态
            return True
            
        except Exception as e:
            logger.error(f"验证登录状态时出错: {str(e)}")
            return False
    
    def is_working_hour(self):
        """
        检查当前是否在工作时间范围内
        
        如果配置了全天运行模式或测试模式，则始终返回True
        否则检查当前时间是否在工作时间范围内
        """
        # 检查是否配置了全天运行模式或测试模式
        if self.config.get('all_day_operation', False) or self.config.get('test_mode', False):
            logger.info("已配置全天运行模式或测试模式，忽略工作时间限制")
            return True
            
        # 获取工作时间配置
        working_hours = self.config.get('working_hours', {'start': 9, 'end': 22})
        start_hour = working_hours.get('start', 9)
        end_hour = working_hours.get('end', 22)
        
        # 检查当前时间是否在工作时间范围内
        current_hour = datetime.now().hour
        if start_hour <= current_hour < end_hour:
            logger.info(f"当前时间 {current_hour}:00 在工作时间范围 {start_hour}:00-{end_hour}:00 内")
            return True
                
        logger.info(f"当前时间 {current_hour}:00 不在工作时间范围 {start_hour}:00-{end_hour}:00 内")
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
        """检查登录状态并等待用户登录"""
        try:
            # 首先检查是否已登录
            if self.verify_login():
                return True
            
            # 如果未登录，提示用户进行登录
            logger.info("请使用抖音APP扫码登录...")
            print("\n" + "="*50)
            print("请使用抖音APP扫描二维码登录")
            print("登录完成后按回车键继续...")
            print("="*50 + "\n")
            
            # 等待用户输入
            input()
            
            # 再次验证登录状态
            if self.verify_login():
                logger.info("登录成功！")
                return True
            
            logger.error("登录失败，请重试")
            return False
            
        except Exception as e:
            logger.error(f"检查登录状态时出错: {str(e)}")
            return False 