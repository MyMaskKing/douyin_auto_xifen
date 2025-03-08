import sqlite3
from datetime import datetime, timedelta
from loguru import logger
import os

class Database:
    def __init__(self):
        # 确保data目录存在
        os.makedirs('data', exist_ok=True)
        self.conn = sqlite3.connect('data/douyin.db')
        self.create_tables()
        
    def create_tables(self):
        """创建必要的数据表"""
        try:
            cursor = self.conn.cursor()
            
            # 关注记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS follows (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    follow_time TIMESTAMP,
                    is_following INTEGER DEFAULT 1
                )
            ''')
            
            # 互动记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action_type TEXT,
                    action_time TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"创建数据表失败: {str(e)}")
            raise
            
    def add_follow_record(self, user_id, username):
        """添加关注记录"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO follows (user_id, username, follow_time, is_following) VALUES (?, ?, ?, 1)",
                (user_id, username, datetime.now())
            )
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"添加关注记录失败: {str(e)}")
            
    def remove_follow_record(self, user_id):
        """更新取关记录"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE follows SET is_following = 0 WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"更新取关记录失败: {str(e)}")
            
    def get_today_follow_count(self):
        """获取今日关注数量"""
        try:
            cursor = self.conn.cursor()
            today = datetime.now().date()
            cursor.execute(
                "SELECT COUNT(*) FROM follows WHERE date(follow_time) = date(?) AND is_following = 1",
                (today,)
            )
            return cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"获取今日关注数量失败: {str(e)}")
            return 0
            
    def get_inactive_users(self, days=3):
        """获取超过指定天数未回关的用户"""
        try:
            cursor = self.conn.cursor()
            cutoff_date = datetime.now() - timedelta(days=days)
            
            cursor.execute("""
                SELECT user_id, username FROM follows 
                WHERE follow_time < ? 
                AND is_following = 1
                ORDER BY follow_time ASC
                LIMIT 100
                """,
                (cutoff_date,)
            )
            
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"获取未回关用户失败: {str(e)}")
            return []
            
    def add_interaction(self, user_id, action_type):
        """记录互动行为"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO interactions (user_id, action_type, action_time) VALUES (?, ?, ?)",
                (user_id, action_type, datetime.now())
            )
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"记录互动行为失败: {str(e)}")
            
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close() 