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
    # 创建日期目录
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = os.path.join("logs", today, "app_logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志
    logger.remove()  # 移除默认处理器
    
    # 添加文件日志处理器
    log_file = os.path.join(log_dir, f"douyin_bot_{datetime.now().strftime('%H-%M-%S')}.log")
    logger.add(
        log_file, 
        rotation="100 MB", 
        level="INFO",
        encoding="utf-8"
    )
    
    # 添加控制台日志处理器
    logger.add(sys.stderr, level="INFO")
    
    logger.info(f"日志文件路径: {log_file}")

# 创建必要的目录
def setup_directories():
    # 创建基本目录
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # 创建日期目录
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 创建分类目录
    categories = ["screenshot", "html", "error", "analysis"]
    operations = ["user_profile", "before_click_fans", "after_click_fans", 
                 "after_js_click_fans", "fans_page", "before_follow", 
                 "after_follow", "error", "fans_elements"]
    
    for category in categories:
        for operation in operations:
            os.makedirs(os.path.join("logs", today, category, operation), exist_ok=True)

def signal_handler(sig, frame):
    """处理程序中断信号"""
    logger.info("接收到中断信号，正在优雅退出...")
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
        bot = DouyinBot(config, db)
        
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
                
                # 根据任务结果决定休息时间
                if task_result and task_result.get('task_type') == 'check_follows':
                    # 如果是检查关注列表任务完成，等待配置的间隔时间
                    interval = task_result.get('interval', 3600)
                    logger.info(f"检查关注列表任务完成，休息 {interval} 秒后执行下一轮任务")
                    time.sleep(interval)
                else:
                    # 其他任务完成后的默认休息时间
                    time.sleep(10)
                
            except Exception as e:
                logger.error(f"运行任务时出错: {str(e)}")
                time.sleep(30)  # 出错后等待较长时间再重试
                
                # 尝试重新连接浏览器
                try:
                    bot.start()
                except:
                    logger.error("重新连接浏览器失败")
                    time.sleep(60)  # 重连失败后等待更长时间
        
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