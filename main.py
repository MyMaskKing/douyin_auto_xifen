#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import signal
import sys
import shutil
from loguru import logger
from core.douyin_bot import DouyinBot
from utils.db import Database
from utils.config import load_config
from utils.paths import *
from datetime import datetime


def get_resource_path(relative_path):
    """获取资源文件路径，兼容开发环境和打包环境"""
    try:
        # PyInstaller创建临时文件夹，将路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    except Exception:
        # 如果不是打包环境，则使用当前目录
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def init_workspace():
    """初始化工作目录"""
    # 创建工作主目录
    workspace_path = get_workspace_path()
    if not os.path.exists(workspace_path):
        os.makedirs(workspace_path)
        logger.info(f"创建工作目录: {workspace_path}")
    
    # 在工作目录下创建子目录
    subdirs = [get_config_path(), get_data_path(), get_logs_path(), get_screenshots_path()]
    for dir_path in subdirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            logger.info(f"创建目录: {dir_path}")
    
    # 检查配置文件和模板文件
    config_file = os.path.join(get_config_path(), 'config.yaml')
    example_config = os.path.join(get_config_path(), 'config.example.yaml')
    
    # 如果模板文件不存在，从打包的文件中复制
    if not os.path.exists(example_config):
        # 获取打包后的模板文件路径
        source_example = get_resource_path(os.path.join('config', 'config.example.yaml'))
        if os.path.exists(source_example):
            shutil.copy2(source_example, example_config)
            logger.info(f"创建配置文件模板: {example_config}")
        else:
            logger.error(f"找不到配置文件模板！路径: {source_example}")
            print("\n错误：找不到配置文件模板，请确保程序完整性后重试")
            sys.exit(1)
    
    # 检查配置文件是否存在
    if not os.path.exists(config_file):
        print("\n" + "="*50)
        print("首次运行需要配置！")
        print(f"请复制配置文件模板: {example_config}")
        print(f"到配置文件: {config_file}")
        print("并按照需求修改配置内容")
        print("修改完成后按回车键继续...")
        print("="*50 + "\n")
        input()
        
        # 再次检查配置文件是否存在
        if not os.path.exists(config_file):
            print("\n错误：未找到配置文件，请确保已复制并修改配置文件后再运行程序")
            logger.error("用户未创建配置文件")
            sys.exit(1)
        
        logger.info("用户已确认配置文件创建完成")
    
    return config_file  # 返回配置文件路径

# 创建分类日志目录
def setup_logging():
    """设置日志配置"""
    # 创建日志目录
    log_dir = os.path.join(get_logs_path(), datetime.now().strftime("%Y-%m-%d"), "app_logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 生成日志文件名
    log_file = os.path.join(log_dir, f"douyin_bot_{datetime.now().strftime('%H-%M-%S')}.log")
    
    # 移除默认的日志处理器
    logger.remove()
    
    # 添加文件日志处理器
    logger.add(
        log_file,
        rotation="500 MB",
        retention="10 days",
        level="INFO",
        encoding="utf-8"
    )
    
    # 添加控制台日志处理器
    logger.add(
        sys.stderr,
        level="INFO"
    )
    
    logger.info(f"日志文件路径: {log_file}")
    return log_file

# 创建必要的目录
def setup_directories():
    """创建必要的目录"""
    dirs = [
        get_logs_path(),
        get_screenshots_path(),
        get_data_path()
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)

def signal_handler(signum, frame):
    """信号处理函数"""
    logger.info(f"收到信号: {signum}")
    if 'bot' in globals():
        bot.stop()
    sys.exit(0)

def main():
    """主函数"""
    try:
        # 初始化工作目录
        config_file = init_workspace()
        
        # 设置日志和目录
        setup_logging()
        setup_directories()
        
        # 注册信号处理
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 加载配置
        config = load_config()
        
        # 初始化数据库
        db = Database()
        
        # 创建机器人实例
        global bot
        bot = DouyinBot(config=config, db=db)
        
        # 启动浏览器
        bot.start()
        
        logger.info("抖音自动涨粉工具已启动")
        
        # 主循环
        while True:
            try:
                # 检查浏览器是否已关闭
                if bot.is_browser_closed():
                    logger.info("浏览器已关闭，程序退出")
                    break
                    
                # 运行任务
                task_result = bot.run_tasks()
                
                # 检查任务执行结果
                if not task_result.get('success', False):
                    error_reason = task_result.get('reason', '未知错误')
                    logger.error(f"任务执行失败: {error_reason}")
                    
                # 等待用户输入决定是否继续
                user_input = input("任务执行遇到问题，是否继续执行？(y/n): ")
                if user_input.lower() != 'y':
                    logger.info("用户选择终止任务")
                    break
                else:
                    logger.info("用户选择继续执行任务")
                
            except Exception as e:
                logger.error(f"运行任务时出错: {str(e)}")
                break  # 发生异常时退出循环
        
    except KeyboardInterrupt:
        logger.info("用户中断，程序退出")
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}")
    finally:
        # 确保程序退出时不关闭浏览器
        if 'bot' in globals():
            bot.stop()
        logger.info("程序已退出")

if __name__ == "__main__":
    main() 