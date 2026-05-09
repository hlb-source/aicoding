"""
opencode执行模块 - 使用适配器隔离外部依赖

改进：
- 使用OpenCodeAdapter替代直接subprocess调用
- 使用OSAdapter替代直接os操作
- 使用LoggingAdapter替代直接logging
- 业务逻辑不依赖外部实现
"""

from typing import Optional
from adapters import (
    AdapterFactory,
    IOpenCodeAdapter,
    IOSAdapter,
    ILoggingAdapter
)


class OpenCodeExecutor:
    """opencode执行器 - 使用适配器隔离依赖"""
    
    def __init__(
        self,
        opencode_path: str = "opencode",
        timeout: int = 60,
        auto_confirm: bool = True,
        workdir: Optional[str] = None,
        opencode_adapter: Optional[IOpenCodeAdapter] = None,
        os_adapter: Optional[IOSAdapter] = None,
        logging_adapter: Optional[ILoggingAdapter] = None
    ):
        """
        初始化opencode执行器
        
        Args:
            opencode_path: opencode可执行文件路径
            timeout: 超时时间
            auto_confirm: 是否自动确认
            workdir: 工作目录
            opencode_adapter: OpenCode适配器（测试时可注入mock）
            os_adapter: OS适配器（测试时可注入mock）
            logging_adapter: Logging适配器（测试时可注入mock）
        """
        self.opencode_path = opencode_path
        self.timeout = timeout
        self.auto_confirm = auto_confirm
        self.workdir = workdir or str(AdapterFactory.create_os_adapter().file_exists('.'))
        
        self.opencode_adapter = opencode_adapter or AdapterFactory.create_opencode_adapter()
        self.os_adapter = os_adapter or AdapterFactory.create_os_adapter()
        self.logging_adapter = logging_adapter or AdapterFactory.create_logging_adapter()
        
        self.logger = self.logging_adapter.get_logger(__name__)
        
        self._validate_opencode()
    
    def _validate_opencode(self) -> None:
        """验证opencode是否可用"""
        if self.opencode_adapter.validate(self.opencode_path):
            self.logger.info(f"opencode验证成功")
        else:
            self.logger.warning(f"opencode验证失败，但仍将尝试执行")
    
    def execute(self, message: str) -> dict:
        """
        执行opencode命令
        
        Args:
            message: 要执行的消息
            
        Returns:
            执行结果
        """
        if not message or not message.strip():
            self.logger.warning("空消息，跳过执行")
            return {
                'success': False,
                'output': '',
                'error': '空消息',
                'returncode': -1
            }
        
        message = message.strip()
        self.logger.info(f"执行命令: {message}")
        
        result = self.opencode_adapter.run(
            opencode_path=self.opencode_path,
            message=message,
            timeout=self.timeout,
            cwd=self.workdir
        )
        
        if result['success']:
            self.logger.info(f"命令执行成功")
            if result['output']:
                self.logger.debug(f"输出: {result['output'][:200]}...")
        else:
            self.logger.error(f"命令执行失败: {result['error']}")
        
        return result
    
    def execute_and_log(self, message: str, log_file: str = "logs/commands.log") -> dict:
        """
        执行命令并记录到日志文件
        
        Args:
            message: 命令消息
            log_file: 日志文件路径
            
        Returns:
            执行结果
        """
        from datetime import datetime
        
        result = self.execute(message)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "SUCCESS" if result['success'] else "FAILED"
        
        log_content = f"\n{'='*60}\n"
        log_content += f"[{timestamp}] {status}\n"
        log_content += f"命令: {message}\n"
        log_content += f"返回码: {result['returncode']}\n"
        if result['output']:
            log_content += f"输出:\n{result['output']}\n"
        if result['error']:
            log_content += f"错误:\n{result['error']}\n"
        log_content += f"{'='*60}\n"
        
        self.os_adapter.write_file(log_file, log_content, mode='a', encoding='utf-8')
        
        self.logger.info(f"命令日志已记录: {log_file}")
        
        return result
    
    def set_workdir(self, workdir: str) -> None:
        """设置工作目录"""
        self.workdir = workdir
        self.logger.info(f"工作目录设置为: {self.workdir}")
    
    def set_timeout(self, timeout: int) -> None:
        """设置超时时间"""
        self.timeout = timeout
        self.logger.info(f"超时时间设置为: {timeout}秒")