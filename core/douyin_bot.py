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
from loguru import logger
import random
import time
import os
from datetime import datetime
from .selectors import USER_PROFILE, COMMON

class DouyinBot:
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.driver = None
        self.wait = None
        self.retry_count = 3
        self.today_follows = 0
        self.today_unfollows = 0
        
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
                if self._verify_login():
                    logger.info("检测到已登录状态！")
                else:
                    # 如果未检测到登录状态，提示用户登录
                    logger.info("未检测到登录状态，请在浏览器中手动登录抖音...")
                    input("登录完成后按回车键继续...")
                    
                    # 再次验证登录状态
                    if not self._verify_login():
                        raise Exception("登录验证失败，请确保已正确登录")
            except Exception as e:
                logger.info(f"登录状态检查失败: {str(e)}")
                logger.info("请在浏览器中手动登录抖音...")
                input("登录完成后按回车键继续...")
                
                # 最后一次验证登录状态
                self._verify_login()
                
            logger.info("登录成功！")
            
            # 加载今日操作数据
            self.today_follows = self.db.get_today_follow_count()
            logger.info(f"今日已关注: {self.today_follows}")
            
        except Exception as e:
            logger.error(f"启动失败: {str(e)}")
            raise
            
    def _verify_login(self):
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
        """检查当前是否在工作时间范围内"""
        current_hour = datetime.now().hour
        for start, end in self.config['working_hours']:
            if start <= current_hour < end:
                return True
        return False
        
    def random_sleep(self, min_time, max_time):
        """随机等待一段时间"""
        time.sleep(random.uniform(min_time, max_time))
        
    def _retry_on_exception(self, func, *args, **kwargs):
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
        
    def visit_user_profile(self, username):
        """访问用户主页"""
        try:
            self.driver.get(f"https://www.douyin.com/user/{username}")
            self.random_sleep(2, 4)
            
            # 等待页面加载完成
            self.wait.until(
                EC.invisibility_of_element_located((By.XPATH, COMMON['LOADING']))
            )
            
        except Exception as e:
            logger.error(f"访问用户主页失败: {str(e)}")
            raise
            
    def _click_fans_tab(self):
        """点击粉丝标签"""
        fans_tab = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, USER_PROFILE['FANS_TAB']))
        )
        fans_tab.click()
        self.random_sleep(1, 2)
        
    def _click_following_tab(self):
        """点击关注标签"""
        following_tab = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, USER_PROFILE['FOLLOWING_TAB']))
        )
        following_tab.click()
        self.random_sleep(1, 2)
        
    def _get_fan_items(self):
        """获取粉丝列表项"""
        return self.wait.until(
            EC.presence_of_all_elements_located((By.XPATH, USER_PROFILE['FAN_ITEM']))
        )
        
    def _get_following_items(self):
        """获取关注列表项"""
        return self.wait.until(
            EC.presence_of_all_elements_located((By.XPATH, USER_PROFILE['FOLLOWING_ITEM']))
        )
        
    def _scroll_list(self, list_selector):
        """滚动列表以加载更多"""
        self.driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollHeight", 
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, list_selector))
            )
        )
        self.random_sleep(1, 2)
        
    def _extract_user_info(self, item):
        """从列表项中提取用户信息"""
        try:
            username = item.find_element(By.XPATH, USER_PROFILE['USERNAME']).text
            user_id = item.find_element(By.XPATH, USER_PROFILE['USER_ID']).text
            # 有时候用户ID会带有@前缀，需要去掉
            if user_id.startswith('@'):
                user_id = user_id[1:]
            return user_id, username
        except NoSuchElementException:
            return None, None
        
    def follow_user(self, fan_item):
        """关注用户"""
        try:
            # 提取用户信息
            user_id, username = self._extract_user_info(fan_item)
            if not user_id:
                return False
                
            # 查找关注按钮
            follow_btn = fan_item.find_element(By.XPATH, USER_PROFILE['FOLLOW_BTN'])
            
            # 检查是否已关注
            if "已关注" in follow_btn.text:
                return False
                
            # 点击关注
            follow_btn.click()
            
            # 记录到数据库
            self.db.add_follow_record(user_id, username)
            
            self.today_follows += 1
            logger.info(f"成功关注用户: {username} ({user_id})，今日已关注: {self.today_follows}")
            
            # 随机等待
            self.random_sleep(*self.config['operation']['follow_interval'])
            return True
            
        except (NoSuchElementException, ElementClickInterceptedException):
            return False
        except Exception as e:
            logger.error(f"关注用户失败: {str(e)}")
            return False
            
    def unfollow_user(self, user_id, username):
        """取消关注用户"""
        try:
            # 访问用户主页
            self.visit_user_profile(user_id)
            
            # 查找取消关注按钮
            unfollow_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, USER_PROFILE['UNFOLLOW_BTN']))
            )
            unfollow_btn.click()
            
            # 确认取消关注
            try:
                confirm_btn = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, USER_PROFILE['CONFIRM_UNFOLLOW_BTN']))
                )
                confirm_btn.click()
            except TimeoutException:
                # 有些情况下可能没有确认对话框
                pass
                
            # 更新数据库
            self.db.remove_follow_record(user_id)
            
            self.today_unfollows += 1
            logger.info(f"已取消关注用户: {username} ({user_id})，今日已取关: {self.today_unfollows}")
            
            # 随机等待
            self.random_sleep(*self.config['operation']['unfollow_interval'])
            return True
            
        except Exception as e:
            logger.error(f"取消关注用户失败: {str(e)}")
            return False
            
    def unfollow_inactive_users(self):
        """取消关注未回关的用户"""
        # 检查浏览器是否已关闭
        if self.is_browser_closed():
            return
            
        if self.today_unfollows >= self.config['operation']['daily_unfollow_limit']:
            logger.info("今日取关已达上限")
            return
            
        # 获取需要取关的用户
        inactive_users = self.db.get_inactive_users(self.config['operation']['unfollow_days'])
        
        if not inactive_users:
            logger.info("没有需要取关的用户")
            return
            
        logger.info(f"发现 {len(inactive_users)} 个超过 {self.config['operation']['unfollow_days']} 天未回关的用户")
        
        # 取关用户
        for user_id, username in inactive_users:
            # 再次检查浏览器是否已关闭
            if self.is_browser_closed():
                return
                
            if self.today_unfollows >= self.config['operation']['daily_unfollow_limit']:
                logger.info("今日取关已达上限")
                break
                
            self._retry_on_exception(self.unfollow_user, user_id, username)
            
    def run_tasks(self):
        """执行主要任务"""
        try:
            # 检查浏览器是否已关闭
            if self.is_browser_closed():
                return
                
            # 先处理取关任务
            self.unfollow_inactive_users()
            
            # 检查今日是否达到关注上限
            if self.today_follows >= self.config['operation']['daily_follow_limit']:
                logger.info("今日关注已达上限")
                return
                
            # 遍历目标用户
            for target_user in self.config['target']['users']:
                # 再次检查浏览器是否已关闭
                if self.is_browser_closed():
                    return
                    
                if self.today_follows >= self.config['operation']['daily_follow_limit']:
                    break
                    
                logger.info(f"正在处理目标用户: {target_user}")
                
                # 访问用户主页
                self._retry_on_exception(self.visit_user_profile, target_user)
                
                # 点击粉丝标签
                self._retry_on_exception(self._click_fans_tab)
                
                # 处理粉丝列表
                scroll_count = 0
                while (self.today_follows < self.config['operation']['daily_follow_limit'] 
                       and scroll_count < 10):
                    # 再次检查浏览器是否已关闭
                    if self.is_browser_closed():
                        return
                        
                    # 获取粉丝列表
                    fan_items = self._retry_on_exception(self._get_fan_items)
                    
                    # 关注粉丝
                    for fan_item in fan_items:
                        # 再次检查浏览器是否已关闭
                        if self.is_browser_closed():
                            return
                            
                        if self.today_follows >= self.config['operation']['daily_follow_limit']:
                            break
                        self._retry_on_exception(self.follow_user, fan_item)
                        
                    # 滚动加载更多
                    self._retry_on_exception(self._scroll_list, USER_PROFILE['FANS_LIST'])
                    scroll_count += 1
                    
        except Exception as e:
            logger.error(f"执行任务失败: {str(e)}")
            
    def stop(self):
        """停止程序并清理资源"""
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")

    def is_browser_closed(self):
        """检查浏览器窗口是否已关闭"""
        try:
            # 尝试获取当前窗口句柄，如果浏览器已关闭会抛出异常
            self.driver.current_window_handle
            return False
        except:
            logger.info("检测到浏览器窗口已关闭")
            return True 