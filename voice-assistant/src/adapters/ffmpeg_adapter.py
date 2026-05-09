"""
FFmpeg适配器 - 隔离FFmpeg工具依赖

功能：
- 封装ffmpeg录音命令
- 封装设备列表查询
- 封装版本验证
"""

from typing import List, Dict, Any
from .subprocess_adapter import SubprocessAdapter


class FFmpegAdapter:
    """FFmpeg适配器实现"""
    
    def __init__(self):
        self.subprocess_adapter = SubprocessAdapter()
    
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
        cmd = [
            ffmpeg_path,
            "-y",
            "-f", "dshow",
            "-i", f"audio={device_name}",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-t", str(duration),
            output_path
        ]
        
        result = self.subprocess_adapter.run_command(
            cmd=cmd,
            timeout=int(duration) + 10
        )
        
        return result['success']
    
    def list_devices(self, ffmpeg_path: str) -> List[str]:
        """
        列出音频设备
        
        Args:
            ffmpeg_path: ffmpeg路径
            
        Returns:
            设备列表
        """
        cmd = [
            ffmpeg_path,
            "-list_devices", "true",
            "-f", "dshow",
            "-i", "dummy"
        ]
        
        result = self.subprocess_adapter.run_command(cmd=cmd, timeout=5)
        
        devices = []
        output = result['stderr']
        
        for line in output.split('\n'):
            if 'audio' in line.lower() or '麦克风' in line.lower() or 'microphone' in line.lower():
                devices.append(line.strip())
        
        return devices
    
    def validate(self, ffmpeg_path: str) -> bool:
        """
        验证ffmpeg可用
        
        Args:
            ffmpeg_path: ffmpeg路径
            
        Returns:
            是否可用
        """
        cmd = [ffmpeg_path, "-version"]
        
        result = self.subprocess_adapter.run_command(cmd=cmd, timeout=5)
        
        return result['success']