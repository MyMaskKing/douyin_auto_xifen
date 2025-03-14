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
            
            # 待关注粉丝表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS follow_fans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    username TEXT,
                    from_type TEXT,  -- 粉丝来源类型：video_comment, video_like, etc.
                    source_id TEXT,  -- 来源ID，如视频ID
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed INTEGER DEFAULT 0,  -- 0: 未处理, 1: 已处理
                    UNIQUE(user_id)
                )
            ''')
            
            # 粉丝记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fans (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    first_seen_time TIMESTAMP,
                    last_seen_time TIMESTAMP,
                    follow_status TEXT,
                    is_processed INTEGER DEFAULT 0,
                    need_follow_back INTEGER DEFAULT 0,
                    follow_back_time TIMESTAMP,
                    days_followed INTEGER DEFAULT 0,  -- 已关注天数
                    last_message_time TIMESTAMP,      -- 最后一次私信时间
                    message_count INTEGER DEFAULT 0,  -- 私信次数
                    is_valid_fan INTEGER DEFAULT 0    -- 是否是有效粉丝
                )
            ''')
            
            # 私信记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    message TEXT,
                    send_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES fans (user_id)
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
                    action_time TIMESTAMP,
                    UNIQUE(user_id, action_type, action_time)
                )
            ''')
            
            # 视频处理记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_videos (
                    video_url TEXT PRIMARY KEY,
                    processed_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success INTEGER DEFAULT 1
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
        """删除用户的关注记录"""
        try:
            cursor = self.conn.cursor()
            
            # 删除用户的关注记录
            cursor.execute(
                "DELETE FROM follows WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
            
            # 检查是否成功删除
            if cursor.rowcount > 0:
                logger.info(f"成功删除用户 {user_id} 的关注记录")
                return True
            else:
                logger.warning(f"未找到用户 {user_id} 的关注记录，无法删除")
                return False
                
        except Exception as e:
            logger.error(f"删除用户关注记录失败: {str(e)}")
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
        """
        获取超过指定天数未回关的用户
        
        参数:
            days: 超过几天未回关则视为不活跃用户
            
        返回:
            包含用户ID和用户名的元组列表 [(user_id, username), ...]
        """
        try:
            cursor = self.conn.cursor()
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 查询超过指定天数的关注记录，且未被标记为待取关的用户
            cursor.execute("""
                SELECT user_id, username FROM follows 
                WHERE date(follow_time) < date(?) 
                AND is_following = 1
                AND (should_unfollow = 0 OR should_unfollow IS NULL)
                ORDER BY follow_time ASC
                LIMIT 100
                """,
                (cutoff_date,)
            )
            
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"获取未回关用户失败: {str(e)}")
            return []
            
    def get_users_to_unfollow(self, limit=100, unfollow_days=3):
        """
        获取需要取关的用户列表
        
        参数:
            limit: 最大返回数量
            unfollow_days: 关注天数阈值，只返回关注时间超过该天数的用户
                          当unfollow_days=0时，返回所有标记为待取关的用户，不考虑关注时间
            
        返回:
            包含用户ID和用户名的字典列表 [{'user_id': '123', 'username': 'user1'}, ...]
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now()
            
            if unfollow_days == 0:
                # 当unfollow_days为0时，返回所有标记为待取关的用户
                cursor.execute(
                    """
                    SELECT user_id, username FROM follows 
                    WHERE is_following = 1 AND should_unfollow = 1
                    ORDER BY marked_for_unfollow_time ASC
                    LIMIT ?
                    """,
                    (limit,)
                )
            else:
                # 计算关注时间阈值
                threshold_date = (now - timedelta(days=unfollow_days))
                
                # 返回关注时间超过阈值且标记为待取关的用户
                cursor.execute(
                    """
                    SELECT user_id, username FROM follows 
                    WHERE is_following = 1 AND should_unfollow = 1 AND date(follow_time) <= date(?)
                    ORDER BY marked_for_unfollow_time ASC
                    LIMIT ?
                    """,
                    (threshold_date, limit)
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
            
    def mark_user_for_unfollow(self, user_id, username, days=3):
        """
        将用户标记为待取关
        
        参数:
            user_id: 用户ID
            username: 用户名
            days: 参数已废弃，保留是为了兼容性，实际判断逻辑已移至get_users_to_unfollow方法
        
        返回:
            bool: 是否成功标记
        """
        try:
            now = datetime.now().isoformat()
            cursor = self.conn.cursor()
            
            # 检查用户是否已在关注列表中
            cursor.execute(
                "SELECT is_following, should_unfollow FROM follows WHERE user_id = ?",
                (user_id,)
            )
            
            result = cursor.fetchone()
            
            if result:
                is_following, should_unfollow = result
                
                # 如果用户已经被取关，不需要再标记
                if is_following == 0:
                    logger.info(f"用户 {username} 已经被取关，不需要再标记")
                    return True
                    
                # 如果用户已经被标记为待取关，不需要再标记
                if should_unfollow == 1:
                    logger.info(f"用户 {username} 已经被标记为待取关")
                    return True
                
                # 标记为待取关
                cursor.execute(
                    "UPDATE follows SET should_unfollow = 1, marked_for_unfollow_time = ? WHERE user_id = ?",
                    (now, user_id)
                )
                self.conn.commit()
                logger.info(f"已标记用户 {username} 为待取关")
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
            
    def mark_user_for_follow_back(self, user_id, username):
        """
        将用户标记为待回关
        
        参数:
            user_id: 用户ID
            username: 用户名
            
        返回:
            bool: 是否成功标记
        """
        try:
            now = datetime.now()
            cursor = self.conn.cursor()
            
            # 检查用户是否已在粉丝表中
            cursor.execute(
                "SELECT follow_status, need_follow_back FROM fans WHERE user_id = ?",
                (user_id,)
            )
            
            result = cursor.fetchone()
            
            if result:
                follow_status, need_follow_back = result
                
                # 如果用户已经被标记为待回关，不需要再标记
                if need_follow_back == 1:
                    logger.info(f"用户 {username} 已经被标记为待回关")
                    return True
                
                # 更新用户状态
                cursor.execute(
                    """
                    UPDATE fans 
                    SET follow_status = ?, need_follow_back = 1, last_seen_time = ?
                    WHERE user_id = ?
                    """,
                    ("need_follow_back", now, user_id)
                )
            else:
                # 添加新的粉丝记录
                cursor.execute(
                    """
                    INSERT INTO fans (
                        user_id, username, first_seen_time, last_seen_time,
                        follow_status, need_follow_back
                    ) VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (user_id, username, now, now, "need_follow_back")
                )
            
            self.conn.commit()
            logger.info(f"已标记用户 {username} 为待回关")
            return True
            
        except Exception as e:
            logger.error(f"标记用户为待回关失败: {str(e)}")
            return False
            
    def get_users_to_follow_back(self, limit=50):
        """
        获取需要回关的用户列表
        
        参数:
            limit: 最大返回数量
            
        返回:
            包含用户ID和用户名的字典列表 [{'user_id': '123', 'username': 'user1'}, ...]
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute(
                """
                SELECT user_id, username 
                FROM fans 
                WHERE need_follow_back = 1 
                AND follow_back_time IS NULL
                ORDER BY first_seen_time ASC
                LIMIT ?
                """,
                (limit,)
            )
            
            return [{'user_id': row[0], 'username': row[1]} for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"获取待回关用户失败: {str(e)}")
            return []
            
    def mark_user_followed_back(self, user_id):
        """
        标记用户已回关
        
        参数:
            user_id: 用户ID
            
        返回:
            bool: 是否成功标记
        """
        try:
            now = datetime.now()
            cursor = self.conn.cursor()
            
            # 更新粉丝记录
            cursor.execute(
                """
                UPDATE fans 
                SET follow_status = 'followed_back',
                    need_follow_back = 0,
                    follow_back_time = ?,
                    is_processed = 1
                WHERE user_id = ?
                """,
                (now, user_id)
            )
            
            # 添加关注记录
            cursor.execute(
                """
                INSERT OR REPLACE INTO follows (
                    user_id, username, follow_time, is_following
                )
                SELECT user_id, username, ?, 1
                FROM fans
                WHERE user_id = ?
                """,
                (now, user_id)
            )
            
            self.conn.commit()
            logger.info(f"已标记用户 {user_id} 为已回关")
            return True
            
        except Exception as e:
            logger.error(f"标记用户已回关失败: {str(e)}")
            return False
            
    def get_today_follow_back_count(self):
        """获取今日回关数量"""
        try:
            cursor = self.conn.cursor()
            today = datetime.now().date()
            
            cursor.execute(
                """
                SELECT COUNT(*) 
                FROM fans 
                WHERE date(follow_back_time) = date(?)
                AND follow_status = 'followed_back'
                """,
                (today,)
            )
            
            return cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"获取今日回关数量失败: {str(e)}")
            return 0
            
    def is_fan_processed(self, user_id):
        """检查粉丝是否已处理过"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT is_processed FROM fans WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            return result and result[0] == 1
            
        except Exception as e:
            logger.error(f"检查粉丝处理状态失败: {str(e)}")
            return False
            
    def get_unprocessed_target_videos(self, target_videos, days=1):
        """
        获取今天未处理的目标视频
        
        参数:
            target_videos: 目标视频列表
            days: 检查最近几天的数据，默认为1天
            
        返回:
            未处理的视频ID列表
        """
        try:
            if not target_videos:
                return []
                
            cursor = self.conn.cursor()
            start_date = (datetime.now() - timedelta(days=days)).date()
            
            # 检查是否存在target_videos表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='target_videos'")
            if not cursor.fetchone():
                # 创建target_videos表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS target_videos (
                        video_id TEXT PRIMARY KEY,
                        processed_time TIMESTAMP,
                        follow_count INTEGER DEFAULT 0,
                        comment_count INTEGER DEFAULT 0
                    )
                ''')
                self.conn.commit()
                logger.info("创建target_videos表")
                return target_videos  # 如果表不存在，返回所有视频
            
            # 构建SQL参数占位符
            placeholders = ','.join(['?'] * len(target_videos))
            
            # 查询在指定时间范围内已处理的视频
            cursor.execute(f"""
                SELECT DISTINCT video_id
                FROM target_videos 
                WHERE video_id IN ({placeholders})
                AND date(processed_time) >= date(?)
            """, target_videos + [start_date])
            
            processed_videos = [row[0] for row in cursor.fetchall()]
            
            # 返回未处理的视频
            return [video for video in target_videos if video not in processed_videos]
            
        except Exception as e:
            logger.error(f"获取未处理目标视频失败: {str(e)}")
            return []
            
    def mark_target_video_processed(self, video_id, follow_count=0, comment_count=0):
        """
        标记视频为已处理
        
        参数:
            video_id: 视频ID
            follow_count: 关注的用户数量
            comment_count: 评论的数量
            
        返回:
            bool: 是否成功标记
        """
        try:
            now = datetime.now()
            cursor = self.conn.cursor()
            
            # 检查是否存在target_videos表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='target_videos'")
            if not cursor.fetchone():
                # 创建target_videos表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS target_videos (
                        video_id TEXT PRIMARY KEY,
                        processed_time TIMESTAMP,
                        follow_count INTEGER DEFAULT 0,
                        comment_count INTEGER DEFAULT 0
                    )
                ''')
                self.conn.commit()
                logger.info("创建target_videos表")
            
            # 插入或更新记录
            cursor.execute(
                "INSERT OR REPLACE INTO target_videos (video_id, processed_time, follow_count, comment_count) VALUES (?, ?, ?, ?)",
                (video_id, now, follow_count, comment_count)
            )
            self.conn.commit()
            logger.info(f"已标记视频 {video_id} 为已处理，关注了 {follow_count} 个用户，评论了 {comment_count} 次")
            return True
            
        except Exception as e:
            logger.error(f"标记视频为已处理失败: {str(e)}")
            return False
            
    def add_comment_record(self, video_id, comment_text):
        """
        添加评论记录
        
        参数:
            video_id: 视频ID
            comment_text: 评论内容
            
        返回:
            bool: 是否成功添加
        """
        try:
            now = datetime.now()
            cursor = self.conn.cursor()
            
            # 检查是否存在comments表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comments'")
            if not cursor.fetchone():
                # 创建comments表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS comments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        video_id TEXT,
                        comment_text TEXT,
                        comment_time TIMESTAMP
                    )
                ''')
                self.conn.commit()
                logger.info("创建comments表")
            
            # 插入评论记录
            cursor.execute(
                "INSERT INTO comments (video_id, comment_text, comment_time) VALUES (?, ?, ?)",
                (video_id, comment_text, now)
            )
            self.conn.commit()
            logger.info(f"已添加视频 {video_id} 的评论记录: {comment_text}")
            return True
            
        except Exception as e:
            logger.error(f"添加评论记录失败: {str(e)}")
            return False
            
    def clear_video_comments(self, days=None):
        """
        清空评论记录
        
        参数:
            days: 清除几天前的评论，如果为None则清除所有评论
            
        返回:
            bool: 是否成功清空
        """
        try:
            cursor = self.conn.cursor()
            
            # 检查是否存在comments表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comments'")
            if not cursor.fetchone():
                logger.info("comments表不存在，无需清空")
                return True
            
            if days is None:
                # 清空所有评论
                cursor.execute("DELETE FROM comments")
                logger.info("已清空所有评论记录")
            else:
                # 清除指定天数前的评论
                cutoff_date = datetime.now() - timedelta(days=days)
                cursor.execute("DELETE FROM comments WHERE date(comment_time) < date(?)", (cutoff_date,))
                logger.info(f"已清除 {days} 天前的评论记录")
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"清空评论记录失败: {str(e)}")
            return False
            
    def get_user_by_id(self, user_id):
        """
        根据用户ID获取用户信息
        
        参数:
            user_id: 用户ID
            
        返回:
            dict: 包含用户信息的字典，如果用户不存在则返回None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM fans WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row))
            return None
            
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return None
        
    # ===== follow_fans表操作方法 =====
    
    def add_follow_fan(self, user_id, username, from_type, source_id=None):
        """添加待关注粉丝"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO follow_fans (user_id, username, from_type, source_id) VALUES (?, ?, ?, ?)",
                (user_id, username, from_type, source_id)
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"添加待关注粉丝失败: {e}")
            return False
            
    def get_unprocessed_follow_fans(self, limit=50):
        """获取未处理的待关注粉丝"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM follow_fans WHERE processed = 0 ORDER BY created_at ASC LIMIT ?",
            (limit,)
        )
        return cursor.fetchall()
        
    def mark_follow_fan_as_processed(self, fan_id):
        """标记待关注粉丝为已处理"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE follow_fans SET processed = 1 WHERE id = ?",
            (fan_id,)
        )
        self.conn.commit()
        
    def delete_follow_fan(self, fan_id):
        """删除待关注粉丝记录"""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM follow_fans WHERE id = ?",
            (fan_id,)
        )
        self.conn.commit()
        
    def is_video_processed(self, video_url):
        """
        检查视频是否已经处理过
        
        参数:
            video_url: 视频链接
            
        返回:
            bool: 是否已处理
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM processed_videos WHERE video_url = ?",
                (video_url,)
            )
            return cursor.fetchone()[0] > 0
            
        except Exception as e:
            logger.error(f"检查视频处理状态失败: {str(e)}")
            return False
            
    def mark_video_processed(self, video_url, success=True):
        """
        标记视频为已处理
        
        参数:
            video_url: 视频链接
            success: 处理是否成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO processed_videos (video_url, processed_time, success) VALUES (?, ?, ?)",
                (video_url, datetime.now(), 1 if success else 0)
            )
            self.conn.commit()
            logger.info(f"已标记视频 {video_url} 为已处理")
            
        except Exception as e:
            logger.error(f"标记视频处理状态失败: {str(e)}")
            
    def add_fan_record(self, user_id, username, follow_status="new_fan"):
        """
        添加新的粉丝记录
        
        参数:
            user_id: 用户ID
            username: 用户名
            follow_status: 关注状态（new_fan/need_follow_back/mutual/requested）
        """
        try:
            now = datetime.now()
            cursor = self.conn.cursor()
            
            # 检查是否已存在该粉丝记录
            cursor.execute("SELECT user_id, follow_status, first_seen_time FROM fans WHERE user_id = ?", (user_id,))
            existing_fan = cursor.fetchone()
            
            if existing_fan:
                # 更新粉丝记录
                cursor.execute(
                    """
                    UPDATE fans 
                    SET last_seen_time = ?,
                        follow_status = ?,
                        need_follow_back = CASE 
                            WHEN ? = 'need_follow_back' THEN 1 
                            ELSE need_follow_back 
                        END
                    WHERE user_id = ?
                    """,
                    (now, follow_status, follow_status, user_id)
                )
                logger.info(f"更新粉丝记录: {username} ({user_id}), 状态: {follow_status}")
            else:
                # 添加新的粉丝记录
                cursor.execute(
                    """
                    INSERT INTO fans (
                        user_id, username, first_seen_time, last_seen_time,
                        follow_status, need_follow_back, days_followed,
                        is_processed, is_valid_fan
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0)
                    """,
                    (user_id, username, now, now, follow_status, 1 if follow_status == "need_follow_back" else 0)
                )
                logger.info(f"添加新粉丝记录: {username} ({user_id}), 状态: {follow_status}")
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"添加粉丝记录失败: {str(e)}")
            return False
            
    def add_message_record(self, user_id, message):
        """添加私信记录"""
        try:
            now = datetime.now()
            cursor = self.conn.cursor()
            
            # 添加私信记录
            cursor.execute(
                "INSERT INTO messages (user_id, message, send_time) VALUES (?, ?, ?)",
                (user_id, message, now)
            )
            
            # 更新粉丝表中的私信相关字段
            cursor.execute(
                """
                UPDATE fans 
                SET last_message_time = ?,
                    message_count = message_count + 1
                WHERE user_id = ?
                """,
                (now, user_id)
            )
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"添加私信记录失败: {str(e)}")
            return False
            
    def get_today_message_count(self):
        """获取今日私信数量"""
        try:
            cursor = self.conn.cursor()
            today = datetime.now().date()
            
            cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE date(send_time) = date(?)",
                (today,)
            )
            return cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"获取今日私信数量失败: {str(e)}")
            return 0
            
    def get_fans_need_message(self, limit=50):
        """
        获取需要发送私信的粉丝
        
        返回：需要发送私信的粉丝列表，每个粉丝包含user_id、username和days_since_follow
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now()
            
            # 获取需要发送私信的粉丝
            cursor.execute(
                """
                SELECT f.user_id, f.username, 
                       CAST((julianday(date(?)) - julianday(date(f.first_seen_time))) AS INTEGER) as days_since_follow
                FROM fans f
                WHERE julianday(date(?)) - julianday(date(f.first_seen_time)) <= 2  -- 处理前三天的粉丝（0,1,2分别代表第一、二、三天）
                AND (
                    f.last_message_time IS NULL  -- 从未发送过私信
                    OR (
                        date(f.last_message_time) < date(?)  -- 今天还没有发送过私信
                        AND julianday(date(?)) - julianday(date(f.last_message_time)) >= 1  -- 距离上次私信至少1天
                    )
                )
                ORDER BY f.first_seen_time ASC
                LIMIT ?
                """,
                (now, now, now, now, limit)
            )
            
            # 获取列名
            columns = [description[0] for description in cursor.description]
            
            # 获取结果
            rows = cursor.fetchall()
            
            # 将结果转换为字典列表
            fans = []
            for row in rows:
                fan_dict = dict(zip(columns, row))
                fans.append(fan_dict)
            
            return fans
            
        except Exception as e:
            logger.error(f"获取需要发送私信的粉丝失败: {str(e)}")
            return []
            
    def update_fan_interaction(self, user_id):
        """更新粉丝互动状态"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now()
            
            # 获取粉丝的first_seen_time
            cursor.execute(
                "SELECT first_seen_time FROM fans WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            if not result:
                logger.error(f"未找到用户 {user_id} 的记录")
                return False
                
            # 计算天数差
            cursor.execute(
                """
                SELECT CAST(julianday(date(?)) - julianday(date(first_seen_time)) AS INTEGER)
                FROM fans WHERE user_id = ?
                """,
                (now, user_id)
            )
            days_since_follow = cursor.fetchone()[0]
            
            # 更新粉丝状态
            cursor.execute(
                """
                UPDATE fans 
                SET days_followed = ?,
                    is_valid_fan = CASE WHEN ? >= 3 THEN 1 ELSE 0 END
                WHERE user_id = ?
                """,
                (days_since_follow, days_since_follow, user_id)
            )
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"更新粉丝互动状态失败: {str(e)}")
            return False 