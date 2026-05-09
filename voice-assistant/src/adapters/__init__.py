"""
适配器层 - 隔离所有外部依赖

架构设计：
- 业务逻辑层 → 适配器接口 → 外部实现
- 业务逻辑不直接依赖外部库
- 适配器提供统一接口
- 方便测试时替换为mock/stub

外部依赖隔离：
- subprocess → SubprocessAdapter
- whisper → WhisperAdapter
- ffmpeg → FFmpegAdapter
- opencode → OpenCodeAdapter
- yaml → YAMLAdapter
- os → OSAdapter
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path


class ISubprocessAdapter(ABC):
    """subprocess适配器接口"""
    
    @abstractmethod
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
        pass


class IWhisperAdapter(ABC):
    """Whisper适配器接口"""
    
    @abstractmethod
    def load_model(self, model_size: str) -> Any:
        """
        加载Whisper模型
        
        Args:
            model_size: 模型大小
            
        Returns:
            模型对象
        """
        pass
    
    @abstractmethod
    def transcribe(
        self,
        model: Any,
        audio_path: str,
        language: Optional[str] = None,
        temperature: float = 0.0,
        initial_prompt: str = ""
    ) -> Dict[str, Any]:
        """
        转录音频
        
        Args:
            model: 模型对象
            audio_path: 音频路径
            language: 语言
            temperature: 温度
            initial_prompt: 提示
            
        Returns:
            {
                'text': str,
                'language': str,
                'segments': list
            }
        """
        pass


class IFFmpegAdapter(ABC):
    """FFmpeg适配器接口"""
    
    @abstractmethod
    def record_audio(
        self,
        ffmpeg_path: str,
        device_name: str,
        duration: float,
        output_path: str,
        sample_rate: int = 16000,
        channels: int = 1
    ) -> bool:
        """
        录制音频
        
        Args:
            ffmpeg_path: ffmpeg路径
            device_name: 设备名称
            duration: 时长
            output_path: 输出路径
            sample_rate: 采样率
            channels: 通道数
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def list_devices(self, ffmpeg_path: str) -> List[str]:
        """
        列出音频设备
        
        Args:
            ffmpeg_path: ffmpeg路径
            
        Returns:
            设备列表
        """
        pass
    
    @abstractmethod
    def validate(self, ffmpeg_path: str) -> bool:
        """
        验证ffmpeg可用
        
        Args:
            ffmpeg_path: ffmpeg路径
            
        Returns:
            是否可用
        """
        pass


class IOpenCodeAdapter(ABC):
    """OpenCode适配器接口"""
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def validate(self, opencode_path: str) -> bool:
        """
        验证opencode可用
        
        Args:
            opencode_path: opencode路径
            
        Returns:
            是否可用
        """
        pass


class IYAMLAdapter(ABC):
    """YAML适配器接口"""
    
    @abstractmethod
    def load(self, file_path: str) -> Dict[str, Any]:
        """
        加载YAML文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            配置字典
        """
        pass
    
    @abstractmethod
    def dump(self, data: Dict[str, Any], file_path: str) -> bool:
        """
        保存YAML文件
        
        Args:
            data: 数据字典
            file_path: 文件路径
            
        Returns:
            是否成功
        """
        pass


class IOSAdapter(ABC):
    """OS适配器接口"""
    
    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            path: 文件路径
            
        Returns:
            是否存在
        """
        pass
    
    @abstractmethod
    def remove_file(self, path: str) -> bool:
        """
        删除文件
        
        Args:
            path: 文件路径
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def get_file_size(self, path: str) -> int:
        """
        获取文件大小
        
        Args:
            path: 文件路径
            
        Returns:
            文件大小
        """
        pass
    
    @abstractmethod
    def create_directory(self, path: str) -> bool:
        """
        创建目录
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def get_temp_file(self, suffix: str = ".wav") -> str:
        """
        获取临时文件路径
        
        Args:
            suffix: 文件后缀
            
        Returns:
            文件路径
        """
        pass
    
    @abstractmethod
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
        pass


class ILoggingAdapter(ABC):
    """Logging适配器接口"""
    
    @abstractmethod
    def setup(
        self,
        log_file: str,
        level: str = 'INFO',
        format: str = None
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
        pass
    
    @abstractmethod
    def get_logger(self, name: str) -> Any:
        """
        获取logger
        
        Args:
            name: logger名称
            
        Returns:
            logger对象
        """
        pass


class ISignalAdapter(ABC):
    """Signal适配器接口"""
    
    @abstractmethod
    def register_handler(self, signum: int, handler: Any) -> bool:
        """
        注册信号处理器
        
        Args:
            signum: 信号编号
            handler: 处理函数
            
        Returns:
            是否成功
        """
        pass


class AdapterFactory:
    """适配器工厂 - 创建适配器实例"""
    
    @staticmethod
    def create_subprocess_adapter() -> ISubprocessAdapter:
        """创建subprocess适配器"""
        from .subprocess_adapter import SubprocessAdapter
        return SubprocessAdapter()
    
    @staticmethod
    def create_whisper_adapter() -> IWhisperAdapter:
        """创建Whisper适配器"""
        from .whisper_adapter import WhisperAdapter
        return WhisperAdapter()
    
    @staticmethod
    def create_ffmpeg_adapter() -> IFFmpegAdapter:
        """创建FFmpeg适配器"""
        from .ffmpeg_adapter import FFmpegAdapter
        return FFmpegAdapter()
    
    @staticmethod
    def create_opencode_adapter() -> IOpenCodeAdapter:
        """创建OpenCode适配器"""
        from .opencode_adapter import OpenCodeAdapter
        return OpenCodeAdapter()
    
    @staticmethod
    def create_yaml_adapter() -> IYAMLAdapter:
        """创建YAML适配器"""
        from .yaml_adapter import YAMLAdapter
        return YAMLAdapter()
    
    @staticmethod
    def create_os_adapter() -> IOSAdapter:
        """创建OS适配器"""
        from .os_adapter import OSAdapter
        return OSAdapter()
    
    @staticmethod
    def create_logging_adapter() -> ILoggingAdapter:
        """创建Logging适配器"""
        from .logging_adapter import LoggingAdapter
        return LoggingAdapter()
    
    @staticmethod
    def create_signal_adapter() -> ISignalAdapter:
        """创建Signal适配器"""
        from .signal_adapter import SignalAdapter
        return SignalAdapter()