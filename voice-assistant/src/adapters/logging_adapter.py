"""
Logging适配器 - 隔离logging模块依赖

功能：
- 封装日志配置
- 封装logger获取
- 提供统一日志接口
"""

import logging
import sys
import io
from typing import Any, Optional
from pathlib import Path


class LoggingAdapter:
    """Logging适配器实现"""
    
    def setup(
        self,
        log_file: Optional[str] = None,
        level: str = 'INFO',
        format: Optional[str] = None
    ) -> bool:
        """
        设置日志
        
        Args:
            log_file: 日志文件（None表示只输出到console）
            level: 日志级别
            format: 日志格式
            
        Returns:
            是否成功
        """
        try:
            log_format = format or '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            log_level = getattr(logging, level.upper(), logging.INFO)
            
            handlers = []
            
            # Console handler with UTF-8 stream
            if sys.platform == 'win32':
                # Windows: Create new UTF-8 stream (don't wrap sys.stdout)
                console_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
                console_handler = logging.StreamHandler(console_stream)
            else:
                # Linux/macOS: Use default stdout
                console_handler = logging.StreamHandler(sys.stdout)
            
            console_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(console_handler)
            
            # File handler with UTF-8 (optional)
            if log_file:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setFormatter(logging.Formatter(log_format))
                handlers.append(file_handler)
            
            # Reset logging configuration
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
            
            logging.basicConfig(
                level=log_level,
                format=log_format,
                handlers=handlers,
                force=True
            )
            
            return True
            
        except Exception as e:
            # Don't use logging here, just print
            print(f"Logging setup error: {e}")
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