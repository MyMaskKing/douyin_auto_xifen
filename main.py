#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import signal
import sys
from loguru import logger
from core.douyin_bot import DouyinBot
from utils.db import Database
from utils.config import load_config
from datetime import datetime

# 创建分类日志目录
def setup_logging():
    """设置日志配置"""
    # 创建日志目录
    log_dir = os.path.join("logs", datetime.now().strftime("%Y-%m-%d"), "app_logs")
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

# 创建必要的目录
def setup_directories():
    """创建必要的目录"""
    dirs = [
        "logs",
        "screenshots",
        "data"
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
    # 设置日志和目录
    setup_logging()
    setup_directories()
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
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
                        continue
                
                # 根据任务结果决定休息时间
                if task_result.get('task_type') == 'check_follows':
                    # 如果是检查关注列表任务完成，等待配置的间隔时间
                    interval = task_result.get('interval', 3600)
                    logger.info(f"检查关注列表任务完成，休息 {interval} 秒后执行下一轮任务")
                    time.sleep(interval)
                else:
                    # 其他任务完成后的默认休息时间
                    time.sleep(10)
                
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