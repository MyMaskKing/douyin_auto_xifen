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

    def is_browser_closed(self):
        """检查浏览器窗口是否已关闭"""
        if self.driver is None:
            logger.info("浏览器未初始化")
            return True
            
        try:
            # 尝试获取当前窗口句柄，如果浏览器已关闭会抛出异常
            self.driver.current_window_handle
            
            # 尝试执行一个简单的JavaScript命令，如果浏览器已关闭会抛出异常
            self.driver.execute_script("return navigator.userAgent")
            
            return False
        except Exception as e:
            logger.info(f"检测到浏览器窗口已关闭: {str(e)}")
            return True 