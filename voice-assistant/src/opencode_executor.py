"""
opencode执行模块 - 调用opencode CLI执行命令

功能：
- 调用opencode run命令
- 超时控制
- 日志记录
- 错误处理
"""

import subprocess
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class OpenCodeExecutor:
    """opencode执行器 - 调用opencode CLI"""
    
    def __init__(
        self,
        opencode_path: str = "opencode",
        timeout: int = 60,
        auto_confirm: bool = True,
        workdir: Optional[str] = None
    ):
        """
        初始化opencode执行器
        
        Args:
            opencode_path: opencode可执行文件路径
            timeout: 超时时间（秒）
            auto_confirm: 是否自动确认
            workdir: 工作目录
        """
        self.opencode_path = opencode_path
        self.timeout = timeout
        self.auto_confirm = auto_confirm
        self.workdir = workdir or str(Path.cwd())
        
        self._validate_opencode()
    
    def _validate_opencode(self) -> None:
        """验证opencode是否可用"""
        try:
            result = subprocess.run(
                [self.opencode_path, "--version"],
                capture_output=True,
                timeout=5,
                cwd=self.workdir
            )
            
            if result.returncode == 0:
                version = result.stdout.decode().strip()
                logger.info(f"opencode验证成功: {version}")
            else:
                logger.warning(f"opencode验证失败，但仍将尝试执行")
                
        except FileNotFoundError:
            logger.warning(f"opencode未找到: {self.opencode_path}")
        except subprocess.TimeoutExpired:
            logger.warning("opencode验证超时")
        except Exception as e:
            logger.warning(f"opencode验证异常: {e}")
    
    def execute(self, message: str) -> dict:
        """
        执行opencode命令
        
        Args:
            message: 要执行的消息/命令
            
        Returns:
            执行结果：
            {
                'success': bool,
                'output': str,
                'error': str,
                'returncode': int
            }
        """
        if not message or not message.strip():
            logger.warning("空消息，跳过执行")
            return {
                'success': False,
                'output': '',
                'error': '空消息',
                'returncode': -1
            }
        
        message = message.strip()
        logger.info(f"执行命令: {message}")
        
        cmd = [self.opencode_path, "run", message]
        
        logger.debug(f"命令: {' '.join(cmd)}")
        logger.debug(f"工作目录: {self.workdir}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.workdir,
                encoding='utf-8',
                errors='ignore'
            )
            
            output = result.stdout.strip()
            error = result.stderr.strip()
            returncode = result.returncode
            
            success = returncode == 0
            
            if success:
                logger.info(f"命令执行成功")
                if output:
                    logger.debug(f"输出: {output[:200]}...")
            else:
                logger.error(f"命令执行失败: {error}")
            
            return {
                'success': success,
                'output': output,
                'error': error,
                'returncode': returncode
            }
            
        except subprocess.TimeoutExpired:
            error_msg = f"命令执行超时（{self.timeout}秒）"
            logger.error(error_msg)
            return {
                'success': False,
                'output': '',
                'error': error_msg,
                'returncode': -1
            }
            
        except FileNotFoundError:
            error_msg = f"opencode未找到: {self.opencode_path}"
            logger.error(error_msg)
            return {
                'success': False,
                'output': '',
                'error': error_msg,
                'returncode': -1
            }
            
        except Exception as e:
            error_msg = f"执行异常: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'output': '',
                'error': error_msg,
                'returncode': -1
            }
    
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
        
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "SUCCESS" if result['success'] else "FAILED"
            
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"[{timestamp}] {status}\n")
                f.write(f"命令: {message}\n")
                f.write(f"返回码: {result['returncode']}\n")
                if result['output']:
                    f.write(f"输出:\n{result['output']}\n")
                if result['error']:
                    f.write(f"错误:\n{result['error']}\n")
                f.write(f"{'='*60}\n")
            
            logger.info(f"命令日志已记录: {log_file}")
            
        except Exception as e:
            logger.warning(f"日志记录失败: {e}")
        
        return result
    
    def set_workdir(self, workdir: str) -> None:
        """设置工作目录"""
        self.workdir = str(Path(workdir).absolute())
        logger.info(f"工作目录设置为: {self.workdir}")
    
    def set_timeout(self, timeout: int) -> None:
        """设置超时时间"""
        self.timeout = timeout
        logger.info(f"超时时间设置为: {timeout}秒")