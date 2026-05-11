"""
音频采集模块 - 使用适配器隔离外部依赖

改进：
- 使用FFmpegAdapter替代直接subprocess调用
- 使用OSAdapter替代直接os操作
- 使用LoggingAdapter替代直接logging
- 业务逻辑不依赖外部实现
"""

from typing import Optional
from adapters import (
    AdapterFactory,
    IFFmpegAdapter,
    IOSAdapter,
    ILoggingAdapter
)


class AudioCapture:
    """音频采集器 - 使用适配器隔离依赖"""
    
    COMMON_DEVICE_NAMES = [
        "麦克风",
        "麦克风 (Realtek High Definition Audio)",
        "麦克风",
        "Microphone",
        "内置麦克风",
        "External Microphone",
    ]
    
    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        sample_rate: int = 16000,
        channels: int = 1,
        device_name: Optional[str] = None,
        archive_enabled: bool = False,
        archive_dir: str = "logs/audio_archive",
        ffmpeg_adapter: Optional[IFFmpegAdapter] = None,
        os_adapter: Optional[IOSAdapter] = None,
        logging_adapter: Optional[ILoggingAdapter] = None
    ):
        """
        初始化音频采集器
        
        Args:
            ffmpeg_path: ffmpeg可执行文件路径
            sample_rate: 采样率
            channels: 通道数
            device_name: 音频设备名称
            archive_enabled: 是否归档录音文件
            archive_dir: 归档目录路径
            ffmpeg_adapter: FFmpeg适配器（测试时可注入mock）
            os_adapter: OS适配器（测试时可注入mock）
            logging_adapter: Logging适配器（测试时可注入mock）
        """
        self.ffmpeg_path = ffmpeg_path
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_name = device_name
        self.archive_enabled = archive_enabled
        self.archive_dir = archive_dir
        
        self.ffmpeg_adapter = ffmpeg_adapter or AdapterFactory.create_ffmpeg_adapter()
        self.os_adapter = os_adapter or AdapterFactory.create_os_adapter()
        self.logging_adapter = logging_adapter or AdapterFactory.create_logging_adapter()
        
        self.logger = self.logging_adapter.get_logger(__name__)
        
        self._validate_ffmpeg()
        
        if not self.device_name:
            self.device_name = self._auto_detect_device()
        
        if self.archive_enabled:
            self.os_adapter.create_directory(self.archive_dir)
            self.logger.info(f"录音归档已启用: {self.archive_dir}")
    
    def _validate_ffmpeg(self) -> None:
        """验证ffmpeg是否可用"""
        if not self.ffmpeg_adapter.validate(self.ffmpeg_path):
            self.logger.error(f"ffmpeg验证失败: {self.ffmpeg_path}")
            raise RuntimeError(f"ffmpeg未找到或不可用: {self.ffmpeg_path}")
        
        self.logger.info("ffmpeg验证成功")
    
    def _auto_detect_device(self) -> str:
        """自动检测音频输入设备"""
        devices = self.list_audio_devices()
        
        for common_name in self.COMMON_DEVICE_NAMES:
            for device in devices:
                if common_name in device or device in common_name:
                    self.logger.info(f"自动检测到设备: {common_name}")
                    return common_name
        
        if devices:
            first_device = devices[0]
            if "audio=" in first_device:
                device_name = first_device.split("audio=")[1].strip()
            else:
                device_name = "麦克风"
            self.logger.info(f"使用首个设备: {device_name}")
            return device_name
        
        self.logger.warning("未检测到音频设备，使用默认名称: 麦克风")
        return "麦克风"
    
    def record_segment(
        self,
        duration: float,
        output_path: Optional[str] = None
    ) -> str:
        """
        录制一段音频
        
        Args:
            duration: 录音时长（秒）
            output_path: 输出文件路径
            
        Returns:
            输出音频文件路径
        """
        from datetime import datetime
        
        start_time = datetime.now()
        
        if output_path is None:
            output_path = self.os_adapter.get_temp_file(suffix=".wav")
        
        self.os_adapter.create_directory(output_path.rsplit('/', 1)[0] if '/' in output_path else '.')
        
        self.logger.info("="*60)
        self.logger.info("【麦克风录音开始】")
        self.logger.info(f"  开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"  录音时长: {duration}秒")
        self.logger.info(f"  音频设备: {self.device_name}")
        self.logger.info(f"  采样率: {self.sample_rate} Hz")
        self.logger.info(f"  通道数: {self.channels}")
        self.logger.info("="*60)
        
        success = self.ffmpeg_adapter.record_audio(
            ffmpeg_path=self.ffmpeg_path,
            device_name=self.device_name,
            duration=duration,
            output_path=output_path,
            sample_rate=self.sample_rate,
            channels=self.channels
        )
        
        end_time = datetime.now()
        
        if not success:
            self.logger.error("录音失败")
            self.logger.info("="*60)
            self.logger.info("【麦克风录音失败】")
            self.logger.info(f"  结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"  失败原因: ffmpeg录音命令执行失败")
            self.logger.info("="*60)
            raise RuntimeError("录音失败")
        
        if not self.os_adapter.file_exists(output_path):
            self.logger.error("录音文件未生成")
            self.logger.info("="*60)
            self.logger.info("【麦克风录音失败】")
            self.logger.info(f"  结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"  失败原因: 音频文件未生成")
            self.logger.info("="*60)
            raise RuntimeError("录音文件未生成")
        
        file_size = self.os_adapter.get_file_size(output_path)
        actual_duration = (end_time - start_time).total_seconds()
        
        self.logger.info("="*60)
        self.logger.info("【麦克风录音完成】")
        self.logger.info(f"  结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"  实际耗时: {actual_duration:.2f}秒")
        self.logger.info(f"  音频文件: {output_path}")
        self.logger.info(f"  文件大小: {file_size} bytes ({file_size/1024:.2f} KB)")
        self.logger.info(f"  音频格式: WAV PCM 16-bit")
        self.logger.info(f"  音频设备: {self.device_name}")
        self.logger.info("="*60)
        
        return output_path
    
    def list_audio_devices(self) -> list:
        """列出可用的音频输入设备"""
        devices = self.ffmpeg_adapter.list_devices(self.ffmpeg_path)
        
        self.logger.info(f"发现 {len(devices)} 个音频设备")
        
        return devices
    
    def cleanup(self, audio_path: str, archive: bool = True) -> str:
        """
        清理或归档临时音频文件
        
        Args:
            audio_path: 音频文件路径
            archive: 是否归档（True=归档，False=删除）
            
        Returns:
            归档文件路径（如果归档）或空字符串（如果删除）
        """
        if archive and self.archive_enabled:
            return self._archive_audio(audio_path)
        else:
            if self.os_adapter.remove_file(audio_path):
                self.logger.info(f"已删除临时文件: {audio_path}")
            else:
                self.logger.warning(f"删除临时文件失败: {audio_path}")
            return ""
    
    def _archive_audio(self, audio_path: str) -> str:
        """
        归档音频文件
        
        Args:
            audio_path: 临时音频文件路径
            
        Returns:
            归档文件路径
        """
        from datetime import datetime
        import shutil
        
        # 创建归档目录
        self.os_adapter.create_directory(self.archive_dir)
        
        # 生成归档文件名（时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_filename = f"audio_{timestamp}.wav"
        archive_path = f"{self.archive_dir}/{archive_filename}"
        
        # 移动文件到归档目录
        try:
            shutil.move(audio_path, archive_path)
            
            file_size = self.os_adapter.get_file_size(archive_path)
            
            self.logger.info("="*60)
            self.logger.info("【录音文件归档】")
            self.logger.info(f"  原始路径: {audio_path}")
            self.logger.info(f"  归档路径: {archive_path}")
            self.logger.info(f"  文件大小: {file_size} bytes ({file_size/1024:.2f} KB)")
            self.logger.info(f"  录音时长: {self.sample_rate}Hz采样")
            self.logger.info("="*60)
            
            return archive_path
            
        except Exception as e:
            self.logger.error(f"归档失败: {e}")
            # 归档失败，删除临时文件
            self.os_adapter.remove_file(audio_path)
            return ""