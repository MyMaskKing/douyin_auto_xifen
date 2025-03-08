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
import sys

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
            # 确保username是字符串类型
            if username is None:
                raise ValueError("用户名不能为空")
                
            username = str(username)  # 确保转换为字符串
            
            # 构建用户主页URL
            user_url = f"https://www.douyin.com/user/{username}"
            logger.info(f"正在访问用户主页: {username}")
            
            # 使用try-except包装导航操作
            try:
                # 访问用户主页
                self.driver.get(user_url)
                logger.info(f"成功导航到URL: {user_url}")
            except Exception as e:
                logger.error(f"导航到URL失败: {str(e)}")
                # 尝试刷新页面
                try:
                    self.driver.refresh()
                    logger.info("刷新页面成功")
                except:
                    logger.error("刷新页面失败")
                    
                # 再次尝试访问
                self.driver.get(user_url)
                logger.info(f"第二次尝试导航到URL: {user_url}")
            
            # 等待页面加载完成
            self.random_sleep(5, 8)  # 增加等待时间
            
            # 检查是否成功加载用户页面
            try:
                # 检查URL是否包含用户ID
                current_url = self.driver.current_url
                if username not in current_url:
                    logger.warning(f"当前URL不包含目标用户ID: {current_url}")
                
                # 检查页面标题
                title = self.driver.title
                logger.info(f"页面标题: {title}")
                
                # 检查是否有错误信息
                error_elements = self.driver.find_elements(By.XPATH, "//div[contains(text(), '错误') or contains(text(), '找不到') or contains(text(), '不存在')]")
                if error_elements:
                    for elem in error_elements:
                        logger.warning(f"页面可能包含错误信息: {elem.text}")
                        
                # 检查是否有用户信息元素
                user_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'author') or contains(@class, 'user')]")
                if not user_elements:
                    logger.warning("未找到用户信息元素")
                else:
                    logger.info(f"找到 {len(user_elements)} 个可能的用户信息元素")
                    
            except Exception as e:
                logger.warning(f"检查页面加载状态时出错: {str(e)}")
            
            # 保存页面截图
            try:
                screenshot_path = f"logs/user_profile_{username}_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"已保存用户主页截图: {screenshot_path}")
            except:
                pass
                
            return True
        except Exception as e:
            logger.error(f"访问用户主页失败: {str(e)}")
            # 保存错误截图
            try:
                screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.error(f"已保存错误截图: {screenshot_path}")
            except:
                pass
            raise
            
    def _click_fans_tab(self):
        """点击粉丝标签"""
        try:
            # 等待页面完全加载
            self.random_sleep(3, 5)
            
            # 记录当前URL
            current_url = self.driver.current_url
            
            # 如果URL中已经包含fans或follower，说明已经在粉丝页面
            if "fans" in current_url or "follower" in current_url:
                logger.info("已经在粉丝页面，无需点击粉丝标签")
                return True
                
            # 尝试直接修改URL方式进入粉丝页面
            try:
                # 从当前URL中提取用户ID
                user_id = current_url.split("/user/")[1].split("?")[0]
                # 构建粉丝页面URL
                fans_url = f"https://www.douyin.com/user/{user_id}?tab=fans"
                # 访问粉丝页面
                self.driver.get(fans_url)
                logger.info("通过URL直接访问粉丝页面")
                self.random_sleep(3, 5)
                return True
            except Exception as e:
                logger.warning(f"通过URL访问粉丝页面失败: {str(e)}，尝试点击方式")
                
            # 尝试点击粉丝标签
            fans_tab = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, USER_PROFILE['FANS_TAB']))
            )
            fans_tab.click()
            logger.info("成功点击粉丝标签")
            self.random_sleep(3, 5)
            return True
            
        except Exception as e:
            logger.error(f"点击粉丝标签失败: {str(e)}")
            # 保存错误截图
            try:
                screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.error(f"已保存错误截图: {screenshot_path}")
            except:
                pass
            raise
        
    def _click_following_tab(self):
        """点击关注标签"""
        try:
            # 等待页面完全加载
            self.random_sleep(3, 5)
            
            # 记录当前URL
            current_url = self.driver.current_url
            
            # 如果URL中已经包含following，说明已经在关注页面
            if "following" in current_url:
                logger.info("已经在关注页面，无需点击关注标签")
                return True
                
            # 尝试直接修改URL方式进入关注页面
            try:
                # 从当前URL中提取用户ID
                user_id = current_url.split("/user/")[1].split("?")[0]
                # 构建关注页面URL
                following_url = f"https://www.douyin.com/user/{user_id}?tab=following"
                # 访问关注页面
                self.driver.get(following_url)
                logger.info("通过URL直接访问关注页面")
                self.random_sleep(3, 5)
                return True
            except Exception as e:
                logger.warning(f"通过URL访问关注页面失败: {str(e)}，尝试点击方式")
                
            # 尝试所有可能的关注标签选择器
            for selector in USER_PROFILE['FOLLOWING_TAB']:
                try:
                    # 尝试常规点击
                    following_tab = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    # 滚动到元素位置
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", following_tab)
                    self.random_sleep(1, 2)
                    
                    # 尝试点击
                    try:
                        following_tab.click()
                        logger.info(f"成功点击关注标签: {selector}")
                        self.random_sleep(3, 5)
                        return True
                    except ElementClickInterceptedException:
                        # 如果常规点击失败，尝试JavaScript点击
                        self.driver.execute_script("arguments[0].click();", following_tab)
                        logger.info(f"使用JavaScript点击关注标签: {selector}")
                        self.random_sleep(3, 5)
                        return True
                        
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
                    continue
                    
            # 如果所有选择器都失败，尝试通过关注数量点击
            try:
                # 查找包含关注数量的元素
                following_count_elements = self.driver.find_elements(By.XPATH, 
                    "//div[contains(text(), '关注') or contains(., '关注')]")
                
                for element in following_count_elements:
                    try:
                        # 滚动到元素位置
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        self.random_sleep(1, 2)
                        
                        # 点击元素
                        element.click()
                        logger.info("通过关注数量元素点击成功")
                        self.random_sleep(3, 5)
                        return True
                    except:
                        # 尝试JavaScript点击
                        try:
                            self.driver.execute_script("arguments[0].click();", element)
                            logger.info("通过JavaScript点击关注数量元素成功")
                            self.random_sleep(3, 5)
                            return True
                        except:
                            continue
            except:
                pass
                
            # 如果所有方法都失败，截图保存
            screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_path)
            logger.error(f"无法找到或点击关注标签，已保存截图: {screenshot_path}")
            
            raise Exception("无法找到或点击关注标签")
            
        except Exception as e:
            logger.error(f"点击关注标签失败: {str(e)}")
            raise
        
    def _get_fan_items(self):
        """获取粉丝列表项"""
        try:
            # 等待页面完全加载
            logger.info("等待页面完全加载...")
            self.random_sleep(8, 10)  # 增加更长的等待时间
            
            # 直接使用JavaScript获取所有可能的粉丝项
            logger.info("尝试使用JavaScript直接获取粉丝项...")
            js_items = self.driver.execute_script("""
                // 查找所有可能的粉丝项
                function findFanItems() {
                    // 常见的用户项选择器
                    var selectors = [
                        'div[class*="user-item"]', 
                        'div[class*="follow-item"]', 
                        'div[class*="user-card"]',
                        'div[class*="card-item"]',
                        'div[data-e2e*="user-item"]',
                        'div[class*="userItem"]',
                        // 抖音特定选择器
                        'div.author-card-user',
                        'div.user-card',
                        'div.user-info-card',
                        'div.user-container',
                        // 通用选择器
                        'div[class*="user"]',
                        'div[class*="follow"]',
                        'div[class*="fans"]'
                    ];
                    
                    // 尝试每个选择器
                    for (var i = 0; i < selectors.length; i++) {
                        var items = document.querySelectorAll(selectors[i]);
                        if (items && items.length > 3) {  // 至少要有几个项才可能是粉丝列表
                            console.log("找到粉丝项: " + selectors[i] + ", 数量: " + items.length);
                            return Array.from(items);
                        }
                    }
                    
                    // 如果上面的方法都失败，尝试查找包含用户名和关注按钮的容器
                    var allDivs = document.querySelectorAll('div');
                    var candidates = [];
                    
                    for (var i = 0; i < allDivs.length; i++) {
                        var div = allDivs[i];
                        // 检查是否包含用户名元素
                        var hasUsername = div.querySelector('span[class*="name"]') || 
                                         div.querySelector('div[class*="name"]') ||
                                         div.querySelector('span[class*="nickname"]') ||
                                         div.querySelector('div[class*="nickname"]');
                                         
                        // 检查是否包含关注按钮
                        var hasFollowBtn = div.querySelector('button') || 
                                          div.querySelector('div[class*="follow"]') ||
                                          div.querySelector('div[role="button"]');
                                          
                        if (hasUsername && hasFollowBtn) {
                            candidates.push(div);
                        }
                    }
                    
                    if (candidates.length > 3) {
                        console.log("通过组合条件找到粉丝项，数量: " + candidates.length);
                        return candidates;
                    }
                    
                    return [];
                }
                
                return findFanItems();
            """)
            
            if js_items and len(js_items) > 0:
                logger.info(f"通过JavaScript成功获取到 {len(js_items)} 个粉丝项")
                return js_items
                
            # 如果JavaScript方法失败，尝试截图并保存页面源码
            logger.error("JavaScript方法获取粉丝列表失败")
            screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_path)
            logger.error(f"已保存截图: {screenshot_path}")
            
            # 保存页面源码
            html_path = f"logs/page_source_{int(time.time())}.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            logger.error(f"已保存页面源码: {html_path}")
            
            raise Exception("无法获取粉丝列表")
            
        except Exception as e:
            logger.error(f"获取粉丝列表失败: {str(e)}")
            # 保存截图
            try:
                screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.error(f"已保存错误截图: {screenshot_path}")
            except:
                pass
            raise
        
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
        """运行任务"""
        # 检查浏览器是否已关闭
        if self.is_browser_closed():
            return
            
        # 检查是否在工作时间
        if not self.is_working_hour():
            return
            
        # 处理取关任务
        if self.is_browser_closed():
            return
            
        try:
            self.unfollow_inactive_users()
        except Exception as e:
            logger.error(f"执行取关任务失败: {str(e)}")
            # 保存错误截图
            try:
                screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.error(f"已保存错误截图: {screenshot_path}")
            except:
                pass
            # 中止程序
            logger.error("由于执行取关任务失败，中止程序")
            sys.exit(1)
            
        # 检查今日关注是否达到上限
        if self.today_follows >= self.config['operation']['daily_follow_limit']:
            logger.info("今日关注已达上限")
            return
            
        # 遍历目标用户
        for target_user in self.config['target']['users']:
            # 检查浏览器是否已关闭
            if self.is_browser_closed():
                return
                
            # 确保target_user是字符串类型
            if target_user is None:
                logger.error("目标用户不能为空")
                # 中止程序
                logger.error("由于目标用户为空，中止程序")
                sys.exit(1)
                
            target_user = str(target_user)  # 确保转换为字符串
            
            try:
                logger.info(f"开始处理目标用户: {target_user}")
                
                # 访问用户主页
                try:
                    self.visit_user_profile(target_user)
                except Exception as e:
                    logger.error(f"访问用户主页失败: {str(e)}")
                    # 保存错误截图
                    try:
                        screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                        self.driver.save_screenshot(screenshot_path)
                        logger.error(f"已保存错误截图: {screenshot_path}")
                    except:
                        pass
                    # 中止程序
                    logger.error("由于访问用户主页失败，中止程序")
                    sys.exit(1)
                
                # 点击粉丝标签
                try:
                    self._click_fans_tab()
                except Exception as e:
                    logger.error(f"点击粉丝标签失败: {str(e)}")
                    # 保存错误截图
                    try:
                        screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                        self.driver.save_screenshot(screenshot_path)
                        logger.error(f"已保存错误截图: {screenshot_path}")
                    except:
                        pass
                    # 中止程序
                    logger.error("由于点击粉丝标签失败，中止程序")
                    sys.exit(1)
                
                # 获取粉丝列表
                fan_count = 0
                max_fans = 50  # 最多处理50个粉丝
                
                # 获取粉丝列表项
                try:
                    fan_items = self._get_fan_items()
                    
                    if not fan_items or len(fan_items) == 0:
                        logger.error(f"获取粉丝列表为空，中止程序")
                        # 保存错误截图
                        try:
                            screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                            self.driver.save_screenshot(screenshot_path)
                            logger.error(f"已保存错误截图: {screenshot_path}")
                        except:
                            pass
                        # 中止程序
                        sys.exit(1)
                        
                    logger.info(f"成功获取到 {len(fan_items)} 个粉丝项")
                    
                except Exception as e:
                    logger.error(f"获取粉丝列表失败: {str(e)}")
                    # 保存错误截图
                    try:
                        screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                        self.driver.save_screenshot(screenshot_path)
                        logger.error(f"已保存错误截图: {screenshot_path}")
                    except:
                        pass
                    # 中止程序
                    logger.error("由于获取粉丝列表失败，中止程序")
                    sys.exit(1)
                
                # 处理粉丝列表
                for fan_item in fan_items:
                    # 检查浏览器是否已关闭
                    if self.is_browser_closed():
                        return
                        
                    # 检查今日关注是否达到上限
                    if self.today_follows >= self.config['operation']['daily_follow_limit']:
                        logger.info("今日关注已达上限")
                        return
                        
                    # 关注用户
                    try:
                        success = self.follow_user(fan_item)
                        
                        if success:
                            fan_count += 1
                            
                        # 如果已经处理了足够多的粉丝，退出循环
                        if fan_count >= max_fans:
                            break
                    except Exception as e:
                        logger.error(f"关注用户失败: {str(e)}")
                        # 保存错误截图
                        try:
                            screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                            self.driver.save_screenshot(screenshot_path)
                            logger.error(f"已保存错误截图: {screenshot_path}")
                        except:
                            pass
                        # 中止程序
                        logger.error("由于关注用户失败，中止程序")
                        sys.exit(1)
                
                logger.info(f"目标用户 {target_user} 处理完成，成功关注 {fan_count} 个粉丝")
                
            except Exception as e:
                logger.error(f"处理目标用户 {target_user} 失败: {str(e)}")
                # 保存截图
                try:
                    screenshot_path = f"logs/error_screenshot_{int(time.time())}.png"
                    self.driver.save_screenshot(screenshot_path)
                    logger.error(f"已保存错误截图: {screenshot_path}")
                except:
                    pass
                
                # 中止程序
                logger.error("由于处理目标用户失败，中止程序")
                sys.exit(1)
                
        logger.info("所有目标用户处理完成")
        
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