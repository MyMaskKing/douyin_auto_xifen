"""
日志系统模块

该模块提供了日志记录、截图保存和HTML源码保存的功能。
"""

from loguru import logger
import sys
import os
import time
from datetime import datetime
import shutil
from utils.paths import get_logs_path

# 配置日志记录器，避免将HTML内容写入app_logs
logger.remove()  # 移除默认处理器
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} - {message}",
    level="INFO"
)
logger.add(
    lambda msg: None if "<html" in msg or "<!DOCTYPE" in msg else msg,  # 过滤HTML内容
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} - {message}",
    level="INFO",
    filter=lambda record: "html" not in record["extra"]
)

# 全局配置对象
_config = None

def set_config(config):
    """设置全局配置对象"""
    global _config
    _config = config
    
    # 更新截图级别
    global SCREENSHOT_LEVEL
    if _config and 'logging' in _config:
        level = _config['logging'].get('screenshot_level', 'NORMAL')
        if level == 'ERROR':
            SCREENSHOT_LEVEL = {
                'ERROR': True,
                'CRITICAL': False,
                'NORMAL': False,
                'DEBUG': False
            }
        elif level == 'CRITICAL':
            SCREENSHOT_LEVEL = {
                'ERROR': True,
                'CRITICAL': True,
                'NORMAL': False,
                'DEBUG': False
            }
        elif level == 'NORMAL':
            SCREENSHOT_LEVEL = {
                'ERROR': True,
                'CRITICAL': True,
                'NORMAL': True,
                'DEBUG': False
            }
        elif level == 'DEBUG':
            SCREENSHOT_LEVEL = {
                'ERROR': True,
                'CRITICAL': True,
                'NORMAL': True,
                'DEBUG': True
            }

# 截图控制变量
SCREENSHOT_LEVEL = {
    'ERROR': True,      # 错误时始终截图
    'CRITICAL': True,   # 关键操作始终截图
    'NORMAL': False,    # 普通操作默认不截图
    'DEBUG': False      # 调试操作默认不截图
}

def cleanup_logs():
    """清理过期的日志文件"""
    try:
        # 使用正确的日志目录路径
        log_dir = get_logs_path()
        
        # 如果目录不存在，直接返回
        if not os.path.exists(log_dir):
            return
            
        # 获取所有日期目录
        date_dirs = [d for d in os.listdir(log_dir) if os.path.isdir(os.path.join(log_dir, d))]
        
        # 按日期排序
        date_dirs.sort(reverse=True)
        
        # 保留最近10天的日志
        keep_days = 10
        if len(date_dirs) > keep_days:
            for old_dir in date_dirs[keep_days:]:
                old_dir_path = os.path.join(log_dir, old_dir)
                try:
                    shutil.rmtree(old_dir_path)
                    logger.info(f"已删除过期日志目录: {old_dir_path}")
                except Exception as e:
                    logger.warning(f"删除日志目录失败: {old_dir_path}, 错误: {str(e)}")
                    
    except Exception as e:
        logger.error(f"清理日志文件失败: {str(e)}")

def get_log_path(log_type, operation=None, user_id=None):
    """
    获取分类整理后的日志文件路径
    
    参数:
        log_type: 日志类型 (screenshot, html, error)
        operation: 操作类型 (follow, unfollow, fans, login, etc.)
        user_id: 用户ID (可选)
    
    返回:
        日志文件路径
    """
    # 创建日期目录
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = os.path.join(get_logs_path(), today)
    
    # 创建日志类型目录
    type_dir = os.path.join(log_dir, log_type)
    
    # 如果有操作类型，创建操作类型目录
    if operation:
        type_dir = os.path.join(type_dir, operation)
        
    # 确保目录存在
    os.makedirs(type_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = int(time.time())
    if user_id:
        filename = f"{user_id}_{timestamp}"
    else:
        filename = f"{timestamp}"
        
    # 根据日志类型确定文件扩展名
    if log_type == "screenshot":
        filename += ".png"
    elif log_type == "html":
        filename += ".html"
    else:
        filename += ".log"
        
    return os.path.join(type_dir, filename)

def save_screenshot(driver, operation, level='NORMAL', user_id=None):
    """
    根据配置的截图级别保存截图
    
    参数:
        driver: WebDriver实例
        operation: 操作类型
        level: 截图级别 (ERROR, CRITICAL, NORMAL, DEBUG)
        user_id: 用户ID (可选)
    
    返回:
        截图路径或None
    """
    if not SCREENSHOT_LEVEL.get(level, False):
        return None
        
    try:
        screenshot_path = get_log_path("screenshot", operation=operation, user_id=user_id)
        driver.save_screenshot(screenshot_path)
        logger.info(f"已保存{operation}截图: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        logger.error(f"保存截图失败: {str(e)}")
        return None

def save_html(driver, operation, user_id=None):
    """
    保存HTML源码
    
    参数:
        driver: WebDriver实例
        operation: 操作类型
        user_id: 用户ID (可选)
    
    返回:
        HTML文件路径或None
    """
    try:
        html_path = get_log_path("html", operation=operation, user_id=user_id)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info(f"已保存{operation}HTML源码: {html_path}")
        return html_path
    except Exception as e:
        logger.error(f"保存HTML源码失败: {str(e)}")
        return None

def save_html_content(html_content, operation, user_id=None):
    """
    保存HTML内容到文件
    
    参数:
        html_content: HTML内容字符串
        operation: 操作类型
        user_id: 用户ID (可选)
    
    返回:
        HTML文件路径或None
    """
    try:
        html_path = get_log_path("html", operation=operation, user_id=user_id)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"已保存{operation}HTML内容: {html_path}")
        return html_path
    except Exception as e:
        logger.error(f"保存HTML内容失败: {str(e)}")
        return None 