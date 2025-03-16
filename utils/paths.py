import os

# 工作目录名称
WORKSPACE_DIR = "douyin_bot_workspace"

def get_abs_path(relative_path):
    """获取绝对路径"""
    # 获取当前脚本所在目录的上级目录作为基础目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.abspath(os.path.join(base_dir, relative_path))

def get_workspace_path():
    """获取工作目录路径"""
    return get_abs_path(WORKSPACE_DIR)

def get_config_path():
    """获取配置文件路径"""
    return get_abs_path(os.path.join(WORKSPACE_DIR, "config"))

def get_data_path():
    """获取数据目录路径"""
    return get_abs_path(os.path.join(WORKSPACE_DIR, "data"))

def get_logs_path():
    """获取日志目录路径"""
    return get_abs_path(os.path.join(WORKSPACE_DIR, "logs"))

def get_screenshots_path():
    """获取截图目录路径"""
    return get_abs_path(os.path.join(WORKSPACE_DIR, "screenshots"))

def get_browser_data_path():
    """获取浏览器数据目录路径"""
    return get_abs_path(os.path.join(WORKSPACE_DIR, "browser_data")) 