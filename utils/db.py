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
                    unfollow_time TIMESTAMP,
                    is_following INTEGER DEFAULT 1,
                    should_unfollow INTEGER DEFAULT 0,
                    marked_for_unfollow_time TIMESTAMP
                )
            ''')
            
            # 检查unfollow_time列是否存在，如果不存在则添加
            cursor.execute("PRAGMA table_info(follows)")
            columns = cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            if 'unfollow_time' not in column_names:
                logger.info("添加unfollow_time列到follows表")
                cursor.execute("ALTER TABLE follows ADD COLUMN unfollow_time TIMESTAMP")
                
            if 'should_unfollow' not in column_names:
                logger.info("添加should_unfollow列到follows表")
                cursor.execute("ALTER TABLE follows ADD COLUMN should_unfollow INTEGER DEFAULT 0")
                
            if 'marked_for_unfollow_time' not in column_names:
                logger.info("添加marked_for_unfollow_time列到follows表")
                cursor.execute("ALTER TABLE follows ADD COLUMN marked_for_unfollow_time TIMESTAMP")
            
            # 互动记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action_type TEXT,
                    action_time TIMESTAMP
                )
            ''')
            
            # 目标用户处理记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS target_users (
                    user_id TEXT PRIMARY KEY,
                    processed_time TIMESTAMP,
                    processed_count INTEGER DEFAULT 0
                )
            ''')
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"创建数据表失败: {str(e)}")
            
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
        """更新用户为已取关状态"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now()
            
            # 更新用户状态为已取关
            cursor.execute(
                "UPDATE follows SET is_following = 0, unfollow_time = ?, should_unfollow = 0 WHERE user_id = ?",
                (now, user_id)
            )
            self.conn.commit()
            
            # 检查是否成功更新
            if cursor.rowcount > 0:
                logger.info(f"成功更新用户 {user_id} 为已取关状态")
                return True
            else:
                logger.warning(f"未找到用户 {user_id} 的关注记录，无法更新为已取关状态")
                return False
                
        except Exception as e:
            logger.error(f"更新用户为已取关状态失败: {str(e)}")
            return False
            
    def get_today_follow_count(self):
        """获取今日关注数量"""
        try:
            cursor = self.conn.cursor()
            today = datetime.now().date()
            cursor.execute(
                "SELECT COUNT(*) FROM follows WHERE date(follow_time) = date(?)",
                (today,)
            )
            return cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"获取今日关注数量失败: {str(e)}")
            return 0
            
    def get_today_unfollow_count(self):
        """获取今日取关数量"""
        try:
            cursor = self.conn.cursor()
            today = datetime.now().date()
            
            # 先检查unfollow_time列是否存在
            cursor.execute("PRAGMA table_info(follows)")
            columns = cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            if 'unfollow_time' not in column_names:
                logger.warning("unfollow_time列不存在，添加该列")
                cursor.execute("ALTER TABLE follows ADD COLUMN unfollow_time TIMESTAMP")
                self.conn.commit()
                return 0
                
            # 查询今日取关数量
            cursor.execute(
                "SELECT COUNT(*) FROM follows WHERE date(unfollow_time) = date(?) AND is_following = 0",
                (today,)
            )
            return cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"获取今日取关数量失败: {str(e)}")
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
            
    def get_users_to_unfollow(self, days=3, limit=100):
        """获取需要取关的用户列表"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT user_id, username FROM follows 
                WHERE is_following = 1 AND should_unfollow = 1
                ORDER BY marked_for_unfollow_time ASC
                LIMIT ?
                """,
                (limit,)
            )
            return [{'user_id': row[0], 'username': row[1]} for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"获取需要取关的用户失败: {str(e)}")
            return []
            
    def is_followed(self, user_id):
        """检查用户是否已经被关注"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM follows WHERE user_id = ? AND is_following = 1",
                (user_id,)
            )
            count = cursor.fetchone()[0]
            return count > 0
            
        except Exception as e:
            logger.error(f"检查用户关注状态失败: {str(e)}")
            return False
            
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
            
    def is_target_user_processed(self, user_id):
        """检查目标用户是否已处理过"""
        try:
            cursor = self.conn.cursor()
            today = datetime.now().date()
            cursor.execute(
                "SELECT COUNT(*) FROM target_users WHERE user_id = ? AND date(processed_time) = date(?)",
                (user_id, today)
            )
            return cursor.fetchone()[0] > 0
            
        except Exception as e:
            logger.error(f"检查目标用户处理状态失败: {str(e)}")
            return False
            
    def mark_target_user_processed(self, user_id, processed_count=0):
        """
        标记目标用户为已处理
        
        参数:
            user_id: 用户ID
            processed_count: 本次处理的粉丝数量
        """
        try:
            cursor = self.conn.cursor()
            
            # 先查询是否已存在记录及当前处理次数
            cursor.execute(
                "SELECT processed_count FROM target_users WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result:
                # 如果存在记录，累加处理次数
                current_count = result[0]
                new_count = current_count + processed_count
                cursor.execute(
                    "UPDATE target_users SET processed_time = ?, processed_count = ? WHERE user_id = ?",
                    (datetime.now(), new_count, user_id)
                )
                logger.info(f"更新目标用户 {user_id} 处理状态，累计处理次数: {new_count}")
            else:
                # 如果不存在记录，创建新记录
                cursor.execute(
                    "INSERT INTO target_users (user_id, processed_time, processed_count) VALUES (?, ?, ?)",
                    (user_id, datetime.now(), processed_count)
                )
                logger.info(f"新增目标用户 {user_id} 处理记录，处理次数: {processed_count}")
                
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"标记目标用户处理状态失败: {str(e)}")
            
    def get_target_user_stats(self, days=7):
        """
        获取目标用户处理统计信息
        
        参数:
            days: 查询最近几天的数据，默认7天
            
        返回:
            包含统计信息的字典列表
        """
        try:
            cursor = self.conn.cursor()
            start_date = (datetime.now() - timedelta(days=days)).date()
            
            cursor.execute("""
                SELECT 
                    user_id, 
                    MAX(processed_time) as last_processed, 
                    SUM(processed_count) as total_processed,
                    COUNT(*) as process_times
                FROM target_users 
                WHERE date(processed_time) >= date(?)
                GROUP BY user_id
                ORDER BY last_processed DESC
            """, (start_date,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'user_id': row[0],
                    'last_processed': row[1],
                    'total_processed': row[2],
                    'process_times': row[3]
                })
                
            return results
            
        except Exception as e:
            logger.error(f"获取目标用户统计信息失败: {str(e)}")
            return []
            
    def get_unprocessed_target_users(self, target_users, days=1):
        """
        获取未处理的目标用户列表
        
        参数:
            target_users: 目标用户ID列表
            days: 查询最近几天未处理的用户，默认1天
            
        返回:
            未处理的目标用户ID列表
        """
        try:
            if not target_users:
                return []
                
            cursor = self.conn.cursor()
            start_date = (datetime.now() - timedelta(days=days)).date()
            
            # 构建SQL参数占位符
            placeholders = ','.join(['?'] * len(target_users))
            
            # 查询在指定时间范围内已处理的用户
            cursor.execute(f"""
                SELECT DISTINCT user_id
                FROM target_users 
                WHERE user_id IN ({placeholders})
                AND date(processed_time) >= date(?)
            """, target_users + [start_date])
            
            processed_users = [row[0] for row in cursor.fetchall()]
            
            # 返回未处理的用户
            return [user for user in target_users if user not in processed_users]
            
        except Exception as e:
            logger.error(f"获取未处理目标用户失败: {str(e)}")
            return []
            
    def mark_user_for_unfollow(self, user_id, username, days=3):
        """
        标记用户为待取关
        
        参数:
            user_id: 用户ID
            username: 用户名
            days: 超过几天未回关则标记为待取关
            
        返回:
            成功返回True，失败返回False
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now()
            
            # 检查用户是否已在关注列表中
            cursor.execute(
                "SELECT follow_time, is_following, should_unfollow FROM follows WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result:
                follow_time, is_following, should_unfollow = result
                
                # 如果用户已经被取关，不需要再标记
                if is_following == 0:
                    logger.info(f"用户 {username} 已经被取关，不需要再标记")
                    return True
                    
                # 如果用户已经被标记为待取关，不需要再标记
                if should_unfollow == 1:
                    logger.info(f"用户 {username} 已经被标记为待取关")
                    return True
                    
                # 检查关注时间是否超过指定天数
                if follow_time:
                    follow_date = datetime.fromisoformat(follow_time)
                    days_followed = (now - follow_date).days
                    
                    if days_followed >= days:
                        # 标记为待取关
                        cursor.execute(
                            "UPDATE follows SET should_unfollow = 1, marked_for_unfollow_time = ? WHERE user_id = ?",
                            (now, user_id)
                        )
                        self.conn.commit()
                        logger.info(f"已标记用户 {username} 为待取关，已关注 {days_followed} 天")
                        return True
                    else:
                        logger.info(f"用户 {username} 关注时间 {days_followed} 天，未达到取关条件 {days} 天")
                        return False
                else:
                    # 如果没有关注时间记录，默认标记为待取关
                    cursor.execute(
                        "UPDATE follows SET should_unfollow = 1, marked_for_unfollow_time = ? WHERE user_id = ?",
                        (now, user_id)
                    )
                    self.conn.commit()
                    logger.info(f"已标记用户 {username} 为待取关（无关注时间记录）")
                    return True
            else:
                # 如果用户不在关注列表中，添加记录并标记为待取关
                cursor.execute(
                    "INSERT INTO follows (user_id, username, follow_time, is_following, should_unfollow, marked_for_unfollow_time) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, username, now, 1, 1, now)
                )
                self.conn.commit()
                logger.info(f"已添加用户 {username} 到关注列表并标记为待取关")
                return True
                
        except Exception as e:
            logger.error(f"标记用户为待取关失败: {str(e)}")
            return False 