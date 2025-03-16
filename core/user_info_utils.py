"""
用户信息提取工具模块

该模块提供了从HTML元素中提取用户信息的共通功能。
"""

from selenium.webdriver.common.by import By
from .logger import logger
import time
import random

class UserInfoUtils:
    """用户信息提取工具类，负责从HTML元素中提取用户信息"""
    
    def __init__(self, driver, wait, random_sleep):
        """
        初始化用户信息提取工具
        
        参数:
            driver: WebDriver对象
            wait: WebDriverWait对象
            random_sleep: 随机等待函数
        """
        self.driver = driver
        self.wait = wait
        self.random_sleep = random_sleep
        
    def extract_user_info_from_element(self, user_item, context=""):
        """
        从HTML元素中提取用户信息
        
        参数:
            user_item: 包含用户信息的HTML元素
            context: 上下文信息，用于日志记录
            
        返回:
            dict: 包含用户信息的字典，如果提取失败则返回None
        """
        try:
            # 提取用户ID - 使用链接href
            user_id = None
            link_element = None
            try:
                # 使用href属性定位用户链接 - 使用第二个链接元素，因为第一个是头像链接
                link_elements = user_item.find_elements(By.XPATH, ".//a[contains(@href, '/user/')]")
                if len(link_elements) >= 2:
                    link_element = link_elements[1]  # 使用第二个链接元素
                elif link_elements:
                    link_element = link_elements[0]  # 如果只有一个，则使用第一个
                else:
                    logger.warning(f"[{context}] 未找到任何链接元素")
                    return None
                
                href = link_element.get_attribute('href')
                if href and '/user/' in href:
                    user_id = href.split('/user/')[-1].split('?')[0]
            except Exception as e:
                logger.warning(f"[{context}] 无法获取用户ID: {str(e)}")
                return None
            
            if not user_id:
                logger.warning(f"[{context}] 未找到用户ID")
                return None
            
            # 提取用户名 - 直接获取最后一个span的值
            username = "未知用户"
            try:
                
                # 获取链接元素内所有span
                all_spans = link_element.find_elements(By.TAG_NAME, "span")
                
                # 直接获取最后一个span的值
                if all_spans:
                    last_span = all_spans[-1]
                    try:
                        text = last_span.text.strip()
                        if text:
                            username = text
                    except Exception as e:
                        logger.info(f"[{context}] 无法获取最后一个span文本: {str(e)}")
            except Exception as e:
                logger.warning(f"[{context}] 无法获取用户名，使用默认值: {username}，错误: {str(e)}")
            
            # 检查关注状态和按钮 - 使用层级结构
            follow_status = "unknown"
            button_element = None
            button_type = None
            try:
                # 使用层级关系获取按钮
                buttons = user_item.find_elements(By.XPATH, ".//button")
                for button in buttons:
                    try:
                        # 获取按钮文本
                        button_text = ""
                        button_divs = button.find_elements(By.XPATH, ".//div")
                        for div in button_divs:
                            div_text = div.text.strip()
                            if div_text:
                                button_text = div_text
                                break
                        
                        if "相互关注" in button_text:
                            follow_status = "mutual"
                            status_text = "相互关注(mutual)"
                            button_type = "mutual"
                            button_element = button
                            break
                        elif "回关" in button_text:
                            follow_status = "need_follow_back"
                            status_text = "待回关(need_follow_back)"
                            button_type = "follow"
                            button_element = button
                            break
                        elif "已关注" in button_text:
                            follow_status = "following"
                            status_text = "已关注(following)"
                            button_type = "unfollow"
                            button_element = button
                            break
                        elif "已请求" in button_text:
                            follow_status = "requested"
                            status_text = "已请求(requested)"
                            button_type = "requested"
                            button_element = button
                            break
                        elif "关注" in button_text:
                            follow_status = "not_following"
                            status_text = "未关注(not_following)"
                            button_type = "follow"
                            button_element = button
                            break
                    except:
                        continue
                
                logger.info(f"[{context}] 用户 {username} ({user_id}) 的关注状态: {status_text}")
            except:
                logger.warning(f"[{context}] 无法获取用户 {username} ({user_id}) 的关注状态")
            
            # 返回提取的用户信息
            return {
                'element': user_item,
                'user_id': user_id,
                'username': username,
                'follow_status': follow_status,
                'button_element': button_element,
                'button_type': button_type
            }
            
        except Exception as e:
            logger.error(f"[{context}] 提取用户信息时出错: {str(e)}")
            return None
            
    def extract_users_from_container(self, container, context=""):
        """
        从容器元素中提取所有用户信息
        
        参数:
            container: 包含用户列表的容器元素
            context: 上下文信息，用于日志记录
            
        返回:
            list: 包含所有用户信息的列表
        """
        try:
            # 使用层级结构定位用户项
            user_items = container.find_elements(By.XPATH, "./div/div[.//a[contains(@href, '/user/')]]")
            if not user_items:
                # 备用选择器
                user_items = container.find_elements(By.XPATH, ".//div[.//a[contains(@href, '/user/')]]")
            
            if not user_items:
                logger.warning(f"[{context}] 未找到任何用户项")
                return []
            
            logger.info(f"[{context}] 找到 {len(user_items)} 个用户项")
            
            # 存储用户信息
            users_info = []
            processed_user_ids = set()  # 用于去重
            
            # 处理每个用户项
            for user_item in user_items:
                try:
                    user_info = self.extract_user_info_from_element(user_item, context)
                    if user_info and user_info['user_id'] not in processed_user_ids:
                        users_info.append(user_info)
                        processed_user_ids.add(user_info['user_id'])
                except Exception as e:
                    logger.warning(f"[{context}] 处理用户项时出错: {str(e)}")
                    continue
            
            logger.info(f"[{context}] 成功提取 {len(users_info)} 个用户信息")
            return users_info
            
        except Exception as e:
            logger.error(f"[{context}] 提取用户列表时出错: {str(e)}")
            return []
    
    def scroll_and_extract_users(self, container, context="", expected_total=0, max_no_new_content=3, scroll_step=100, min_wait=2, max_wait=3, max_retries=3):
        """
        滚动容器并提取用户信息
        
        参数:
            container: 需要滚动的容器元素
            context: 上下文信息，用于日志记录
            expected_total: 预期的用户总数，达到此数量后停止滚动
            max_no_new_content: 连续多少次没有新内容时停止滚动
            scroll_step: 每次滚动的像素数
            min_wait: 最小等待时间
            max_wait: 最大等待时间
            max_retries: 最大重试次数
            
        返回:
            tuple: (用户信息列表, 是否成功)
        """
        try:
            # 初始化变量
            last_height = 0
            no_new_height_count = 0
            retry_count = 0
            
            logger.info(f"[{context}] 开始滚动到底部...")
            
            # 1. 先滚动到底部
            while True:
                try:
                    # 获取当前高度
                    current_height = self.driver.execute_script("return arguments[0].scrollHeight", container)
                    
                    # 检查是否到达底部
                    if current_height == last_height:
                        no_new_height_count += 1
                        if no_new_height_count >= max_no_new_content:
                            logger.info(f"[{context}] 连续{max_no_new_content}次滚动高度未变化，已到达底部")
                            break
                    else:
                        no_new_height_count = 0
                    
                    # 执行平滑滚动
                    current_scroll = self.driver.execute_script("return arguments[0].scrollTop", container)
                    target_scroll = current_height
                    
                    while current_scroll < target_scroll:
                        current_scroll = min(current_scroll + scroll_step, target_scroll)
                        self.driver.execute_script("arguments[0].scrollTop = arguments[1]", container, current_scroll)
                        time.sleep(0.5)
                    
                    # 等待新内容加载
                    self.random_sleep(min_wait, max_wait)
                    last_height = current_height
                    
                except Exception as e:
                    logger.warning(f"[{context}] 滚动操作失败: {str(e)}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(f"[{context}] 达到最大重试次数 ({max_retries})，停止滚动")
                        break
                    continue
            
            # 2. 滚动完成后，获取所有用户信息
            logger.info(f"[{context}] 滚动完成，开始提取用户信息...")
            
            # 使用层级结构定位用户项
            user_items = container.find_elements(By.XPATH, "./div/div[.//a[contains(@href, '/user/')]]")
            if not user_items:
                # 备用选择器
                user_items = container.find_elements(By.XPATH, ".//div[.//a[contains(@href, '/user/')]]")
            
            if not user_items:
                logger.warning(f"[{context}] 未找到任何用户项")
                return [], True
            
            # 存储用户信息
            users_info = []
            processed_user_ids = set()  # 用于去重
            
            # 处理所有用户项
            for user_item in user_items:
                try:
                    user_info = self.extract_user_info_from_element(user_item, "")  # 不传递context避免重复日志
                    if user_info and user_info['user_id'] not in processed_user_ids:
                        users_info.append(user_info)
                        processed_user_ids.add(user_info['user_id'])
                except Exception as e:
                    logger.warning(f"[{context}] 处理用户项时出错: {str(e)}")
                    continue
            
            # 检查是否获取到足够的用户
            if expected_total > 0:
                if len(users_info) >= expected_total:
                    logger.info(f"[{context}] 已获取预期数量的用户 ({len(users_info)}/{expected_total})")
                else:
                    logger.warning(f"[{context}] 未能获取预期数量的用户，当前 {len(users_info)}/{expected_total}")
            
            logger.info(f"[{context}] 共获取 {len(users_info)} 个不重复用户信息")
            return users_info, True
            
        except Exception as e:
            logger.error(f"[{context}] 滚动并提取用户失败: {str(e)}")
            return [], False 