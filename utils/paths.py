import os
import sys
from core.logger import logger
def is_frozen():
    """判断是否在打包环境中运行"""
    return getattr(sys, 'frozen', False)

# 根据环境设置工作目录
if is_frozen():
    # 如果是打包环境，使用可执行文件所在目录下的douyin_bot_workspace
    WORKSPACE_DIR = os.path.join(os.path.dirname(sys.executable), "douyin_bot_workspace")
    logger.info(f"当前工作目录：{WORKSPACE_DIR}")
else:
    # 如果是开发环境，使用项目根目录
    WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logger.info(f"当前工作目录：{WORKSPACE_DIR}")

def get_workspace_path():
    """获取工作目录路径"""
    return WORKSPACE_DIR

def get_config_path():
    """获取配置文件路径"""
    return os.path.join(WORKSPACE_DIR, "config")

def get_data_path():
    """获取数据目录路径"""
    return os.path.join(WORKSPACE_DIR, "data")

def get_logs_path():
    """获取日志目录路径"""
    return os.path.join(WORKSPACE_DIR, "logs")

def get_screenshots_path():
    """获取截图目录路径"""
    return os.path.join(WORKSPACE_DIR, "screenshots")

def get_browser_data_path():
    """获取浏览器数据目录路径"""
    return os.path.join(WORKSPACE_DIR, "browser_data") 
