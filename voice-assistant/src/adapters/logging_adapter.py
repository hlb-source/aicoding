"""
Logging适配器 - 隔离logging模块依赖

功能：
- 封装日志配置
- 封装logger获取
- 提供统一日志接口
"""

import logging
import sys
from typing import Any, Optional
from pathlib import Path


class LoggingAdapter:
    """Logging适配器实现"""
    
    def setup(
        self,
        log_file: str,
        level: str = 'INFO',
        format: Optional[str] = None
    ) -> bool:
        """
        设置日志
        
        Args:
            log_file: 日志文件
            level: 日志级别
            format: 日志格式
            
        Returns:
            是否成功
        """
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            
            log_format = format or '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            log_level = getattr(logging, level.upper(), logging.INFO)
            
            logging.basicConfig(
                level=log_level,
                format=log_format,
                handlers=[
                    logging.FileHandler(log_file, encoding='utf-8'),
                    logging.StreamHandler(sys.stdout)
                ]
            )
            
            return True
            
        except Exception:
            return False
    
    def get_logger(self, name: str) -> Any:
        """
        获取logger
        
        Args:
            name: logger名称
            
        Returns:
            logger对象
        """
        return logging.getLogger(name)