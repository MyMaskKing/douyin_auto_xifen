import yaml
from loguru import logger
import os
from .paths import get_config_path

def load_config(config_path=None):
    """加载配置文件"""
    if config_path is None:
        config_path = os.path.join(get_config_path(), "config.yaml")
        
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
    
    # 验证功能开关配置
    features = config.get('features', {})
    
    # 验证三大类任务的功能开关
    task_categories = ['video_tasks', 'follow_list_tasks', 'fan_list_tasks']
    for category in task_categories:
        if category not in features:
            features[category] = {'enabled': False}
        elif not isinstance(features[category], dict):
            features[category] = {'enabled': bool(features[category])}
        elif 'enabled' not in features[category]:
            features[category]['enabled'] = True
    
    # 验证视频评论功能配置
    if (features.get('video_tasks', {}).get('enabled', False) and 
        (features.get('video_tasks', {}).get('get_video_reviewers', False) or 
         features.get('video_tasks', {}).get('follow_video_fans', False))):
        if 'target_videos' not in config:
            raise ValueError("启用了视频评论或视频评论关注功能但未配置target_videos")
        if not config['target_videos']:
            raise ValueError("启用了视频评论或视频评论关注功能但未配置任何目标视频")
    
    # 验证操作配置
    operation = config.get('operation', {})
    
    # 确保三大类任务的操作配置存在
    for category in task_categories:
        if category not in operation:
            operation[category] = {}
    
    # 确保通用操作配置存在
    if 'common' not in operation:
        operation['common'] = {}
    
    # 验证视频任务操作配置
    video_tasks_op = operation.get('video_tasks', {})
    if 'daily_follow_limit' not in video_tasks_op:
        video_tasks_op['daily_follow_limit'] = 200
    elif not isinstance(video_tasks_op['daily_follow_limit'], int) or video_tasks_op['daily_follow_limit'] <= 0:
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
    
    # 设置默认操作配置
    default_operation = {
        'video_tasks': {
            'follow_fans_batch_size': 100,
            'max_follow_per_video': 1000,
            'batch_rest_interval': [180, 300],
            'user_interval': [60, 180],
            'batch_size_before_rest': 20,
            'daily_follow_limit': 200
        },
        'follow_list_tasks': {
            'daily_unfollow_limit': 100,
            'unfollow_interval': [5, 15],
            'unfollow_days': 3,
            'unfollow_batch_size': 10,
            'min_unfollow_success_rate': 0.7
        },
        'fan_list_tasks': {
            'follow_interval': [30, 60],
            'max_messages_per_day': 100
        },
        'common': {
            'task_interval': 3600
        }
    }
    
    # 合并默认配置
    for category, defaults in default_operation.items():
        if category not in operation:
            operation[category] = {}
        
        for key, value in defaults.items():
            if key not in operation[category]:
                operation[category][key] = value 