"""
OpenCode适配器 - 隔离opencode CLI依赖

功能：
- 封装opencode run命令
- 封装版本验证
- 统一执行接口
"""

from typing import Dict, Any, Optional
from .subprocess_adapter import SubprocessAdapter


class OpenCodeAdapter:
    """OpenCode适配器实现"""
    
    def __init__(self):
        self.subprocess_adapter = SubprocessAdapter()
    
    def run(
        self,
        opencode_path: str,
        message: str,
        timeout: int = 60,
        cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行opencode run命令
        
        Args:
            opencode_path: opencode路径
            message: 消息内容
            timeout: 超时时间
            cwd: 工作目录
            
        Returns:
            {
                'success': bool,
                'output': str,
                'error': str,
                'returncode': int
            }
        """
        cmd = [opencode_path, "run", message]
        
        result = self.subprocess_adapter.run_command(
            cmd=cmd,
            timeout=timeout,
            cwd=cwd
        )
        
        return {
            'success': result['success'],
            'output': result['stdout'],
            'error': result['stderr'],
            'returncode': result['returncode']
        }
    
    def validate(self, opencode_path: str) -> bool:
        """
        验证opencode可用
        
        Args:
            opencode_path: opencode路径
            
        Returns:
            是否可用
        """
        cmd = [opencode_path, "--version"]
        
        result = self.subprocess_adapter.run_command(cmd=cmd, timeout=5)
        
        return result['success']