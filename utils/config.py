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
    required_sections = ['account', 'target', 'operation']
    
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
        
    # 验证工作时间配置 - 支持两种格式
    # 1. 新格式: working_hours: {start: 9, end: 22}
    # 2. 旧格式: working_hours: [[9, 22]]
    if 'working_hours' in config:
        if isinstance(config['working_hours'], dict):
            # 新格式
            if 'start' not in config['working_hours'] or 'end' not in config['working_hours']:
                raise ValueError("工作时间配置缺少start或end字段")
                
            start = config['working_hours']['start']
            end = config['working_hours']['end']
            
            if not (0 <= start < 24 and 0 <= end <= 24 and start < end):
                raise ValueError("工作时间范围必须在0-24之间，且开始时间必须小于结束时间")
                
            logger.info(f"使用工作时间配置: {start}:00 - {end}:00")
            
        elif isinstance(config['working_hours'], list):
            # 旧格式
            # 将旧格式转换为新格式
            if not config['working_hours']:
                logger.info("未配置工作时间，将使用全天运行模式")
                config['working_hours'] = {'start': 0, 'end': 24}
            else:
                time_ranges = []
                for time_range in config['working_hours']:
                    if not isinstance(time_range, list) or len(time_range) != 2:
                        raise ValueError("工作时间配置格式错误")
                        
                    start, end = time_range
                    if not (0 <= start < 24 and 0 <= end <= 24 and start < end):
                        raise ValueError("工作时间范围必须在0-24之间，且开始时间必须小于结束时间")
                        
                    time_ranges.append((start, end))
                    
                # 使用第一个时间范围作为工作时间
                if time_ranges:
                    start, end = time_ranges[0]
                    config['working_hours'] = {'start': start, 'end': end}
                    logger.info(f"将旧格式工作时间配置转换为新格式: {start}:00 - {end}:00")
        else:
            raise ValueError("工作时间配置格式错误")
    else:
        # 如果没有配置工作时间，使用默认值
        config['working_hours'] = {'start': 9, 'end': 22}
        logger.info("未配置工作时间，使用默认值: 9:00 - 22:00")
        
    # 检查全天运行模式
    if 'all_day_operation' in config and config['all_day_operation']:
        logger.info("已配置全天运行模式，将忽略工作时间限制")
        
    # 检查测试模式
    if 'test_mode' in config and config['test_mode']:
        logger.info("已配置测试模式，将忽略工作时间限制") 