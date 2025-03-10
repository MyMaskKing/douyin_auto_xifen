"""
抖音机器人主模块

该模块是抖音自动化操作的主入口，组合其他模块的功能。
"""

from .browser import BrowserManager
from .user_profile import UserProfileManager
from .fan_manager import FanManager
from .follow_manager import FollowListManager
from .task_runner import TaskRunner
from .logger import logger

class DouyinBot:
    """抖音机器人主类，组合其他模块的功能"""
    
    def __init__(self, config, db):
        """
        初始化抖音机器人
        
        参数:
            config: 配置对象
            db: 数据库对象
        """
        self.config = config
        self.db = db
        self.browser_manager = None
        self.user_profile_manager = None
        self.fan_manager = None
        self.follow_manager = None
        self.task_runner = None
        
    def start(self):
        """
        启动抖音机器人
        
        返回:
            成功返回True，失败抛出异常
        """
        try:
            # 初始化浏览器管理器
            self.browser_manager = BrowserManager(self.config, self.db)
            self.driver, self.wait = self.browser_manager.start()
            
            # 初始化用户资料管理器
            self.user_profile_manager = UserProfileManager(self.browser_manager)
            
            # 初始化粉丝管理器
            self.fan_manager = FanManager(self.browser_manager, self.user_profile_manager)
            
            # 初始化关注管理器
            self.follow_manager = FollowListManager(self.browser_manager, self.db, self.config)
            
            # 初始化任务运行器
            self.task_runner = TaskRunner(
                self.browser_manager,
                self.user_profile_manager,
                self.fan_manager,
                self.follow_manager,
                self.db,
                self.config
            )
            
            logger.info("抖音机器人启动成功")
            return True
        except Exception as e:
            logger.error(f"抖音机器人启动失败: {str(e)}")
            raise
            
    def run_tasks(self):
        """
        运行任务
        
        返回:
            成功返回True，失败返回False
        """
        if not self.task_runner:
            logger.error("任务运行器未初始化，请先调用start方法")
            return False
            
        return self.task_runner.run_tasks()
        
    def stop(self):
        """
        停止抖音机器人
        
        返回:
            成功返回True，失败返回False
        """
        try:
            if self.browser_manager:
                self.browser_manager.stop()
                
            logger.info("抖音机器人停止成功")
            return True
        except Exception as e:
            logger.error(f"抖音机器人停止失败: {str(e)}")
            return False
            
    def is_browser_closed(self):
        """
        检查浏览器是否已关闭
        
        返回:
            浏览器已关闭返回True，否则返回False
        """
        if not self.browser_manager:
            return True
            
        return self.browser_manager.is_browser_closed() 