import yaml
from loguru import logger
import os

def load_config():
    """加载配置文件"""
    try:
        config_path = os.path.join('config', 'config.yaml')
        
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
    required_sections = ['account', 'target', 'operation', 'working_hours', 'interaction', 'device']
    
    for section in required_sections:
        if section not in config:
            raise ValueError(f"配置文件缺少必要的{section}配置段")
            
    # 验证目标用户配置
    if not config['target']['users']:
        raise ValueError("请至少配置一个目标用户")
        
    # 验证操作配置
    operation = config['operation']
    if not isinstance(operation['daily_follow_limit'], int) or operation['daily_follow_limit'] <= 0:
        raise ValueError("daily_follow_limit必须是正整数")
        
    # 验证工作时间配置
    for time_range in config['working_hours']:
        if not isinstance(time_range, list) or len(time_range) != 2:
            raise ValueError("工作时间配置格式错误")
        start, end = time_range
        if not (0 <= start < 24 and 0 <= end < 24 and start < end):
            raise ValueError("工作时间范围必须在0-23之间，且开始时间必须小于结束时间") 