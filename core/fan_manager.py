"""
粉丝管理模块

该模块提供了获取和处理粉丝列表的功能。
"""

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
from .logger import logger, save_screenshot, save_html, get_log_path
import json

class FanManager:
    """粉丝管理类，负责获取和处理粉丝列表"""
    
    def __init__(self, browser_manager, user_profile_manager):
        """
        初始化粉丝管理器
        
        参数:
            browser_manager: 浏览器管理器对象
            user_profile_manager: 用户资料管理器对象
        """
        self.browser_manager = browser_manager
        self.user_profile_manager = user_profile_manager
        self.driver = browser_manager.driver
        self.wait = browser_manager.wait
        self.random_sleep = browser_manager.random_sleep
        
    def get_fan_items(self):
        """
        获取粉丝列表项
        
        返回:
            粉丝项列表，每项包含元素、按钮和名称
        """
        try:
            # 等待页面完全加载
            logger.info("等待页面完全加载...")
            self.random_sleep(8, 10)  # 增加更长的等待时间
            
            # 保存页面截图和源码，用于分析
            save_screenshot(self.driver, "fans_page", level="NORMAL")
            save_html(self.driver, "fans_page")
            
            # 检查URL是否包含粉丝标签参数
            current_url = self.driver.current_url
            if "tab=fans_tab" not in current_url and "follower" not in current_url:
                logger.warning("当前URL不包含粉丝标签参数，尝试点击粉丝标签...")
                self.user_profile_manager.click_fans_tab()
                # 点击后重新加载页面
                self.random_sleep(5, 8)
                # 再次保存页面截图和源码
                save_screenshot(self.driver, "fans_page_after_click", level="NORMAL")
                save_html(self.driver, "fans_page_after_click")
            
            # 分析页面结构
            logger.info("分析页面结构，查找粉丝列表...")
            page_structure = self.driver.execute_script("""
                // 分析页面结构
                function analyzePage() {
                    var result = {
                        title: document.title,
                        url: window.location.href,
                        hasFansList: false,
                        fansCount: 0,
                        possibleFansContainers: []
                    };
                    
                    // 检查URL是否包含fans_tab参数
                    if (window.location.href.includes('fans_tab') || 
                        window.location.href.includes('follower')) {
                        result.hasFansList = true;
                    }
                    
                    // 查找可能的粉丝数量元素
                    var fansCountElements = [];
                    var allElements = document.querySelectorAll('*');
                    for (var i = 0; i < allElements.length; i++) {
                        var element = allElements[i];
                        if (element.textContent && element.textContent.includes('粉丝')) {
                            fansCountElements.push({
                                text: element.textContent.trim(),
                                tag: element.tagName,
                                class: element.className
                            });
                        }
                    }
                    result.fansCountElements = fansCountElements;
                    
                    // 查找可能的粉丝列表容器
                    var containers = [];
                    var listSelectors = [
                        'div.user-list', 
                        'div.fans-list', 
                        'div.follow-list',
                        'div.scroll-container',
                        'div[class*="userList"]',
                        'div[class*="user-list"]',
                        'div[class*="fans-list"]',
                        'div[class*="follow-list"]',
                        'div[class*="scroll-container"]'
                    ];
                    
                    listSelectors.forEach(function(selector) {
                        var elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            for (var i = 0; i < elements.length; i++) {
                                containers.push({
                                    selector: selector,
                                    childCount: elements[i].children.length,
                                    hasFollowButtons: elements[i].querySelectorAll('div[data-e2e="user-info-follow"]').length > 0 || 
                                                     elements[i].querySelectorAll('button:contains("关注")').length > 0,
                                    class: elements[i].className
                                });
                            }
                        }
                    });
                    result.possibleFansContainers = containers;
                    
                    // 查找所有关注按钮 - 新版抖音使用div而不是button
                    var followButtons = document.querySelectorAll('div[data-e2e="user-info-follow"], button:contains("关注")');
                    var followButtonsInfo = [];
                    for (var i = 0; i < followButtons.length; i++) {
                        var button = followButtons[i];
                        var buttonText = button.textContent || "";
                        
                        // 检查是否是关注按钮（不是已关注）
                        if ((button.getAttribute('data-e2e') === 'user-info-follow') || 
                            (buttonText.includes('关注') && !buttonText.includes('已关注'))) {
                            
                            // 查找按钮的父元素，可能是用户卡片
                            var parent = button.parentElement;
                            var grandParent = parent ? parent.parentElement : null;
                            var greatGrandParent = grandParent ? grandParent.parentElement : null;
                            
                            followButtonsInfo.push({
                                text: buttonText.trim(),
                                class: button.className,
                                dataE2e: button.getAttribute('data-e2e') || '',
                                parentClass: parent ? parent.className : '',
                                grandParentClass: grandParent ? grandParent.className : '',
                                greatGrandParentClass: greatGrandParent ? greatGrandParent.className : ''
                            });
                        }
                    }
                    result.followButtonsInfo = followButtonsInfo;
                    
                    return result;
                }
                
                return analyzePage();
            """)
            
            # 记录页面分析结果
            logger.info(f"页面标题: {page_structure.get('title', 'N/A')}")
            logger.info(f"页面URL: {page_structure.get('url', 'N/A')}")
            logger.info(f"是否包含粉丝列表参数: {page_structure.get('hasFansList', False)}")
            
            # 记录粉丝数量元素
            fans_count_elements = page_structure.get('fansCountElements', [])
            if fans_count_elements:
                logger.info(f"找到 {len(fans_count_elements)} 个可能的粉丝数量元素:")
                for i, elem in enumerate(fans_count_elements[:3]):  # 只记录前3个，减少日志量
                    logger.info(f"  元素 {i+1}: 文本='{elem.get('text', 'N/A')}', 标签={elem.get('tag', 'N/A')}, 类名={elem.get('class', 'N/A')}")
            
            # 记录可能的粉丝列表容器
            containers = page_structure.get('possibleFansContainers', [])
            if containers:
                logger.info(f"找到 {len(containers)} 个可能的粉丝列表容器:")
                for i, container in enumerate(containers[:3]):  # 只记录前3个，减少日志量
                    logger.info(f"  容器 {i+1}: 选择器={container.get('selector', 'N/A')}, 子元素数量={container.get('childCount', 0)}, 包含关注按钮={container.get('hasFollowButtons', False)}, 类名={container.get('class', 'N/A')}")
            
            # 记录关注按钮信息
            follow_buttons_info = page_structure.get('followButtonsInfo', [])
            if follow_buttons_info:
                logger.info(f"找到 {len(follow_buttons_info)} 个关注按钮:")
                for i, button in enumerate(follow_buttons_info[:3]):  # 只记录前3个，减少日志量
                    logger.info(f"  按钮 {i+1}: 文本='{button.get('text', 'N/A')}', 类名={button.get('class', 'N/A')}, data-e2e={button.get('dataE2e', 'N/A')}")
            
            # 保存分析结果到文件
            analysis_path = get_log_path("analysis", operation="page_structure")
            with open(analysis_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(page_structure, indent=2, ensure_ascii=False))
            logger.info(f"已保存页面结构分析结果: {analysis_path}")
            
            # 检查是否需要点击粉丝标签
            if not page_structure.get('hasFansList', False) and not follow_buttons_info:
                logger.info("当前页面不是粉丝列表页面，尝试点击粉丝标签...")
                self.user_profile_manager.click_fans_tab()
                # 点击后重新加载页面
                self.random_sleep(5, 8)
                return self.get_fan_items()
            
            # 尝试查找粉丝列表中的用户项
            logger.info("尝试使用精确的JavaScript获取粉丝项...")
            
            # 尝试滚动页面以加载更多粉丝
            logger.info("滚动页面以加载更多粉丝...")
            self.driver.execute_script("""
                // 滚动页面以加载更多内容
                function scrollPage() {
                    var scrollHeight = document.body.scrollHeight;
                    var scrollStep = Math.floor(scrollHeight / 10);
                    var scrollPosition = 0;
                    
                    for (var i = 0; i < 5; i++) {
                        scrollPosition += scrollStep;
                        window.scrollTo(0, scrollPosition);
                        // 等待一小段时间让内容加载
                        var waitTime = 500;
                        var startTime = new Date().getTime();
                        while (new Date().getTime() < startTime + waitTime) {}
                    }
                    
                    // 滚动回顶部
                    window.scrollTo(0, 0);
                }
                
                scrollPage();
            """)
            self.random_sleep(3, 5)
            
            # 使用JavaScript查找粉丝列表中的用户项 - 适配新版抖音DOM结构
            fan_items = self.driver.execute_script("""
                // 查找粉丝列表中的用户项
                function findFanItems() {
                    // 查找所有关注按钮 - 新版抖音使用div而不是button
                    var followButtons = document.querySelectorAll('div[data-e2e="user-info-follow"]');
                    var userItems = [];
                    
                    // 如果找不到新版按钮，尝试查找旧版按钮
                    if (followButtons.length === 0) {
                        console.log("未找到新版关注按钮，尝试查找旧版按钮");
                        followButtons = document.querySelectorAll('button');
                        for (var i = 0; i < followButtons.length; i++) {
                            var button = followButtons[i];
                            if (button.textContent && button.textContent.includes('关注') && 
                                !button.textContent.includes('已关注')) {
                                
                                // 查找按钮的父元素，可能是用户卡片
                                var parent = findUserCardParent(button);
                                
                                if (parent) {
                                    // 查找用户名元素
                                    var nameElement = findNameElement(parent);
                                    var name = nameElement ? nameElement.textContent.trim() : "未知用户";
                                    
                                    userItems.push({
                                        element: parent,
                                        button: button,
                                        name: name
                                    });
                                }
                            }
                        }
                    } else {
                        console.log("找到 " + followButtons.length + " 个新版关注按钮");
                        // 处理新版抖音DOM结构
                        for (var i = 0; i < followButtons.length; i++) {
                            var button = followButtons[i];
                            
                            // 查找按钮的父元素，可能是用户卡片
                            var parent = findUserCardParent(button);
                            
                            if (parent) {
                                // 查找用户名元素
                                var nameElement = findNameElement(parent);
                                var name = nameElement ? nameElement.textContent.trim() : "未知用户";
                                
                                userItems.push({
                                    element: parent,
                                    button: button,
                                    name: name
                                });
                            }
                        }
                    }
                    
                    console.log("找到 " + userItems.length + " 个用户项");
                    return userItems;
                }
                
                // 查找用户卡片父元素
                function findUserCardParent(element) {
                    var parent = element.parentElement;
                    var maxDepth = 10; // 防止无限循环
                    var depth = 0;
                    
                    // 向上查找，直到找到包含用户名的元素
                    while (parent && depth < maxDepth) {
                        // 检查是否包含用户名元素
                        if (findNameElement(parent)) {
                            return parent;
                        }
                        
                        parent = parent.parentElement;
                        depth++;
                    }
                    
                    // 如果没有找到合适的父元素，返回原始元素的父元素
                    return element.parentElement;
                }
                
                // 查找用户名元素
                function findNameElement(parent) {
                    // 尝试多种可能的用户名选择器
                    var nameSelectors = [
                        'span[class*="name"]', 
                        'div[class*="name"]', 
                        'span[class*="nickname"]', 
                        'div[class*="nickname"]',
                        'span[class*="title"]',
                        'div[class*="title"]'
                    ];
                    
                    for (var i = 0; i < nameSelectors.length; i++) {
                        var nameElement = parent.querySelector(nameSelectors[i]);
                        if (nameElement && nameElement.textContent.trim()) {
                            return nameElement;
                        }
                    }
                    
                    return null;
                }
                
                return findFanItems();
            """)
            
            if fan_items and len(fan_items) > 0:
                logger.info(f"通过JavaScript成功获取到 {len(fan_items)} 个粉丝项")
                # 记录找到的粉丝项
                for i, item in enumerate(fan_items[:5]):  # 只记录前5个，减少日志量
                    logger.info(f"  粉丝 {i+1}: 名称='{item.get('name', 'N/A')}'")
                return fan_items
            else:
                logger.warning("未能通过JavaScript获取到粉丝项，尝试使用Selenium查找...")
                
                # 尝试使用Selenium查找粉丝项
                try:
                    # 尝试查找新版抖音关注按钮
                    follow_buttons = self.driver.find_elements(By.XPATH, '//div[@data-e2e="user-info-follow"]')
                    
                    # 如果没有找到新版按钮，尝试查找旧版按钮
                    if not follow_buttons:
                        logger.info("未找到新版关注按钮，尝试查找旧版按钮")
                        follow_buttons = self.driver.find_elements(By.XPATH, '//button[contains(text(), "关注") and not(contains(text(), "已关注"))]')
                    
                    if follow_buttons:
                        logger.info(f"通过Selenium找到 {len(follow_buttons)} 个关注按钮")
                        
                        # 将按钮转换为用户项
                        fan_items = []
                        for button in follow_buttons:
                            # 查找按钮的父元素，可能是用户卡片
                            parent = button
                            for _ in range(5):  # 最多向上查找5层
                                parent = parent.find_element(By.XPATH, '..')
                                
                                # 尝试查找用户名元素
                                try:
                                    name_element = parent.find_element(By.XPATH, './/span[contains(@class, "name") or contains(@class, "nickname") or contains(@class, "title")]')
                                    if name_element:
                                        fan_items.append({
                                            "element": parent,
                                            "button": button,
                                            "name": name_element.text.strip()
                                        })
                                        break
                                except NoSuchElementException:
                                    continue
                        
                        logger.info(f"通过Selenium成功获取到 {len(fan_items)} 个粉丝项")
                        # 记录找到的粉丝项
                        for i, item in enumerate(fan_items[:5]):  # 只记录前5个，减少日志量
                            logger.info(f"  粉丝 {i+1}: 名称='{item.get('name', 'N/A')}'")
                        return fan_items
                    else:
                        # 如果仍然找不到关注按钮，尝试直接查找用户卡片
                        logger.warning("未找到任何关注按钮，尝试直接查找用户卡片...")
                        user_cards = self.driver.find_elements(By.XPATH, '//div[contains(@class, "user-item") or contains(@class, "user-card")]')
                        
                        if user_cards:
                            logger.info(f"找到 {len(user_cards)} 个用户卡片")
                            
                            # 将用户卡片转换为用户项
                            fan_items = []
                            for card in user_cards:
                                try:
                                    # 尝试查找关注按钮
                                    button = card.find_element(By.XPATH, './/div[@data-e2e="user-info-follow"] | .//button[contains(text(), "关注") and not(contains(text(), "已关注"))]')
                                    
                                    # 尝试查找用户名元素
                                    try:
                                        name_element = card.find_element(By.XPATH, './/span[contains(@class, "name") or contains(@class, "nickname") or contains(@class, "title")] | .//div[contains(@class, "name") or contains(@class, "nickname") or contains(@class, "title")]')
                                        
                                        fan_items.append({
                                            "element": card,
                                            "button": button,
                                            "name": name_element.text.strip()
                                        })
                                    except NoSuchElementException:
                                        # 尝试使用更精确的选择器
                                        try:
                                            # 根据提供的HTML结构，使用更精确的选择器
                                            username_selectors = [
                                                './/span[contains(@class, "arnSiSbK")]',
                                                './/a[contains(@class, "uz1VJwFY")]//span//span[contains(@class, "arnSiSbK")]',
                                                './/div[contains(@class, "kUKK9Qal")]//a//span//span[contains(@class, "arnSiSbK")]',
                                                './/div[contains(@class, "X8ljGzft")]//div[contains(@class, "kUKK9Qal")]//a//span',
                                                './/a[contains(@href, "/user/")]//span'
                                            ]
                                            
                                            username = "未知用户"
                                            for selector in username_selectors:
                                                name_elements = card.find_elements(By.XPATH, selector)
                                                if name_elements:
                                                    text_content = name_elements[0].text.strip()
                                                    if text_content:
                                                        username = text_content
                                                        logger.info(f"通过选择器 {selector} 找到用户名: {username}")
                                                        break
                                            
                                            # 如果上述方法未能提取用户名，尝试使用JavaScript
                                            if username == "未知用户":
                                                try:
                                                    username = self.driver.execute_script("""
                                                        var element = arguments[0];
                                                        // 尝试查找arnSiSbK类的span元素
                                                        var nameElements = element.querySelectorAll('span.arnSiSbK');
                                                        if (nameElements.length > 0) {
                                                            return nameElements[0].textContent.trim();
                                                        }
                                                        
                                                        // 尝试查找所有嵌套的span元素
                                                        var spans = element.querySelectorAll('span span span');
                                                        for (var i = 0; i < spans.length; i++) {
                                                            var text = spans[i].textContent.trim();
                                                            if (text && text.length > 0) {
                                                                return text;
                                                            }
                                                        }
                                                        
                                                        return "未知用户";
                                                    """, card)
                                                    if username != "未知用户":
                                                        logger.info(f"通过JavaScript找到用户名: {username}")
                                                except Exception as e:
                                                    logger.warning(f"使用JavaScript提取用户名失败: {str(e)}")
                                            
                                            fan_items.append({
                                                "element": card,
                                                "button": button,
                                                "name": username
                                            })
                                        except Exception as e:
                                            logger.warning(f"提取用户名失败: {str(e)}")
                                except NoSuchElementException:
                                    # 如果找不到关注按钮，跳过此卡片
                                    continue
                            
                            if fan_items:
                                logger.info(f"通过用户卡片成功获取到 {len(fan_items)} 个粉丝项")
                                # 记录找到的粉丝项
                                for i, item in enumerate(fan_items[:5]):  # 只记录前5个，减少日志量
                                    logger.info(f"  粉丝 {i+1}: 名称='{item.get('name', 'N/A')}'")
                                return fan_items
                        
                        # 如果所有方法都失败，尝试重新点击粉丝标签
                        logger.warning("所有方法都失败，尝试重新点击粉丝标签...")
                        self.user_profile_manager.click_fans_tab()
                        self.random_sleep(5, 8)
                        
                        # 再次尝试查找关注按钮
                        follow_buttons = self.driver.find_elements(By.XPATH, '//div[@data-e2e="user-info-follow"] | //button[contains(text(), "关注") and not(contains(text(), "已关注"))]')
                        
                        if follow_buttons:
                            logger.info(f"重新点击后找到 {len(follow_buttons)} 个关注按钮")
                            
                            # 将按钮转换为用户项
                            fan_items = []
                            for button in follow_buttons:
                                # 查找按钮的父元素，可能是用户卡片
                                parent = button
                                for _ in range(5):  # 最多向上查找5层
                                    parent = parent.find_element(By.XPATH, '..')
                                    
                                    # 尝试查找用户名元素
                                    try:
                                        name_element = parent.find_element(By.XPATH, './/span[contains(@class, "name") or contains(@class, "nickname") or contains(@class, "title")]')
                                        if name_element:
                                            fan_items.append({
                                                "element": parent,
                                                "button": button,
                                                "name": name_element.text.strip()
                                            })
                                            break
                                    except NoSuchElementException:
                                        continue
                            
                            logger.info(f"重新点击后成功获取到 {len(fan_items)} 个粉丝项")
                            return fan_items
                        
                        logger.warning("未找到任何关注按钮或用户卡片")
                        return []
                        
                except Exception as e:
                    logger.error(f"使用Selenium查找粉丝项失败: {str(e)}")
                    save_screenshot(self.driver, "error", level="ERROR")
                    return []
                
        except Exception as e:
            logger.error(f"获取粉丝列表项失败: {str(e)}")
            # 保存错误截图
            save_screenshot(self.driver, "error", level="ERROR")
            return []