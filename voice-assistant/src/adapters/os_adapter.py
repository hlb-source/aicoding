"""
OS适配器 - 隔离os模块依赖

功能：
- 封装文件操作
- 封装目录操作
- 封装临时文件
"""

import os
import tempfile
from typing import Optional
from pathlib import Path


class OSAdapter:
    """OS适配器实现"""
    
    def file_exists(self, path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            path: 文件路径
            
        Returns:
            是否存在
        """
        return Path(path).exists()
    
    def remove_file(self, path: str) -> bool:
        """
        删除文件
        
        Args:
            path: 文件路径
            
        Returns:
            是否成功
        """
        try:
            if Path(path).exists():
                os.remove(path)
            return True
        except Exception:
            return False
    
    def get_file_size(self, path: str) -> int:
        """
        获取文件大小
        
        Args:
            path: 文件路径
            
        Returns:
            文件大小
        """
        try:
            return Path(path).stat().st_size
        except Exception:
            return 0
    
    def create_directory(self, path: str) -> bool:
        """
        创建目录
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False
    
    def get_temp_file(self, suffix: str = ".wav") -> str:
        """
        获取临时文件路径
        
        Args:
            suffix: 文件后缀
            
        Returns:
            文件路径
        """
        return tempfile.mktemp(suffix=suffix)
    
    def write_file(
        self,
        path: str,
        content: str,
        mode: str = 'a',
        encoding: str = 'utf-8'
    ) -> bool:
        """
        写入文件
        
        Args:
            path: 文件路径
            content: 内容
            mode: 模式
            encoding: 编码
            
        Returns:
            是否成功
        """
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, mode, encoding=encoding) as f:
                f.write(content)
            
            return True
        except Exception:
            return False