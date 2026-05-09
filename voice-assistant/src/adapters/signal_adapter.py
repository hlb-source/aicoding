"""
Signal适配器 - 隔离signal模块依赖

功能：
- 封装信号处理注册
- 提供统一接口
"""

import signal
from typing import Any


class SignalAdapter:
    """Signal适配器实现"""
    
    def register_handler(self, signum: int, handler: Any) -> bool:
        """
        注册信号处理器
        
        Args:
            signum: 信号编号
            handler: 处理函数
            
        Returns:
            是否成功
        """
        try:
            signal.signal(signum, handler)
            return True
        except Exception:
            return False