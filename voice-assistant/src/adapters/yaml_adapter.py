"""
YAML适配器 - 隔离yaml依赖

功能：
- 封装yaml.safe_load()
- 封装yaml.dump()
- 提供文件读写接口
"""

import yaml
from typing import Dict, Any
from pathlib import Path


class YAMLAdapter:
    """YAML适配器实现"""
    
    def load(self, file_path: str) -> Dict[str, Any]:
        """
        加载YAML文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            配置字典
        """
        path = Path(file_path)
        
        if not path.exists():
            return {}
        
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def dump(self, data: Dict[str, Any], file_path: str) -> bool:
        """
        保存YAML文件
        
        Args:
            data: 数据字典
            file_path: 文件路径
            
        Returns:
            是否成功
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            
            return True
            
        except Exception:
            return False