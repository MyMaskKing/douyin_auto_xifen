import yaml
from loguru import logger
import os

def load_config(config_path="config/config.yaml"):
    """加载配置文件"""
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError("配置文件不存在，请复制config.example.yaml为config.yaml并进行配置")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        validate_config(config)
        return config
        
    except Exception as e:
        logger.error(f"加载配置文件失败: {str(e)}")
        raise

def validate_config(config):
    """验证配置文件的完整性"""
    required_sections = ['account', 'operation', 'features']
    
    for section in required_sections:
        if section not in config:
            raise ValueError(f"配置文件缺少必要的{section}配置段")
            
    # 验证视频评论功能配置
    if config.get('features', {}).get('comment_video', False) or config.get('features', {}).get('follow_video_fans', False):
        if 'target_videos' not in config:
            raise ValueError("启用了视频评论或视频评论关注功能但未配置target_videos")
        if not config['target_videos']:
            raise ValueError("启用了视频评论或视频评论关注功能但未配置任何目标视频")
        
    # 验证操作配置
    operation = config['operation']
    if not isinstance(operation['daily_follow_limit'], int) or operation['daily_follow_limit'] <= 0:
        raise ValueError("daily_follow_limit必须是正整数")
        
    # 验证工作时间配置
    if 'working_hours' in config:
        if isinstance(config['working_hours'], dict):
            if 'start' not in config['working_hours'] or 'end' not in config['working_hours']:
                raise ValueError("工作时间配置缺少start或end字段")
                
            start = config['working_hours']['start']
            end = config['working_hours']['end']
            
            if not (0 <= start < 24 and 0 <= end <= 24 and start < end):
                raise ValueError("工作时间范围必须在0-24之间，且开始时间必须小于结束时间")
                
            logger.info(f"使用工作时间配置: {start}:00 - {end}:00")
    else:
        # 如果没有配置工作时间，使用默认值
        config['working_hours'] = {'start': 9, 'end': 22}
        logger.info("未配置工作时间，使用默认值: 9:00 - 22:00")
        
    # 检查全天运行模式
    if config.get('all_day_operation', False):
        logger.info("已配置全天运行模式，将忽略工作时间限制")
        
    # 检查测试模式
    if config.get('test_mode', False):
        logger.info("已配置测试模式，将忽略工作时间限制")
        
    # 验证功能开关配置
    if 'features' not in config:
        config['features'] = {}
    features = config['features']
    
    # 设置默认值
    default_features = {
        'follow_fans': False,
        'check_follows': False,
        'unfollow_users': False,
        'check_fans': False,
        'follow_back': False,
        'follow_video_fans': False,
        'comment_video': False,
        'extract_commenters': False,
        'process_follow_fans': False
    }
    
    for feature, default_value in default_features.items():
        if feature not in features:
            features[feature] = default_value
            
    # 验证操作配置的默认值
    default_operation = {
        'daily_follow_limit': 150,
        'daily_unfollow_limit': 100,
        'follow_interval': 30,
        'unfollow_interval': [5, 15],
        'max_follow_per_video': 20,
        'max_comment_per_day': 10
    }
    
    for key, default_value in default_operation.items():
        if key not in operation:
            operation[key] = default_value 