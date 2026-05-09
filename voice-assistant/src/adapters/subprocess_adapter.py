"""
Subprocess适配器 - 隔离subprocess依赖

功能：
- 封装subprocess.run()
- 统一错误处理
- 提供清晰返回格式
"""

import subprocess
from typing import Any, Dict, List, Optional


class SubprocessAdapter:
    """Subprocess适配器实现"""
    
    def run_command(
        self,
        cmd: List[str],
        timeout: Optional[int] = None,
        capture_output: bool = True,
        text: bool = True,
        cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行外部命令
        
        Args:
            cmd: 命令列表
            timeout: 超时时间（秒）
            capture_output: 是否捕获输出
            text: 是否文本模式
            cwd: 工作目录
            
        Returns:
            {
                'returncode': int,
                'stdout': str,
                'stderr': str,
                'success': bool
            }
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=text,
                timeout=timeout,
                cwd=cwd,
                encoding='utf-8' if text else None,
                errors='ignore' if text else None
            )
            
            return {
                'returncode': result.returncode,
                'stdout': result.stdout if result.stdout else '',
                'stderr': result.stderr if result.stderr else '',
                'success': result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': f'命令超时（{timeout}秒）',
                'success': False
            }
            
        except FileNotFoundError:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': f'命令未找到: {cmd[0]}',
                'success': False
            }
            
        except Exception as e:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': f'执行异常: {str(e)}',
                'success': False
            }