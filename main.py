from loguru import logger
import time
from core.douyin_bot import DouyinBot
from utils.config import load_config
from utils.db import Database

def main():
    # 加载配置
    config = load_config()
    
    # 初始化数据库
    db = Database()
    
    # 初始化机器人
    bot = DouyinBot(config, db)
    
    try:
        # 启动机器人
        bot.start()
        
        # 执行主要任务
        while True:
            # 检查浏览器是否已关闭
            if bot.is_browser_closed():
                logger.info("浏览器已关闭，程序退出")
                break
                
            # 检查是否在运行时间范围内
            if bot.is_working_hour():
                # 执行涨粉任务
                bot.run_tasks()
            else:
                logger.info("当前不在工作时间范围内，休息中...")
                
            # 短暂休息，避免CPU占用过高，同时可以检测浏览器关闭状态
            time.sleep(10)
                
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序发生错误: {str(e)}")
    finally:
        # 清理资源
        bot.stop()
        db.close()

if __name__ == "__main__":
    logger.add("logs/runtime_{time}.log", rotation="1 day")
    main() 