"""
音频采集模块 - 使用ffmpeg录制音频

功能：
- 使用ffmpeg命令行工具从麦克风录音
- 输出WAV格式（Whisper支持的格式）
- 支持分段录音
- 自动设备检测
"""

import subprocess
import os
import logging
import tempfile
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioCapture:
    """音频采集器 - 使用ffmpeg录制音频"""
    
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
        device_index: Optional[int] = None
    ):
        """
        初始化音频采集器
        
        Args:
            ffmpeg_path: ffmpeg可执行文件路径
            sample_rate: 采样率（默认16000，Whisper要求）
            channels: 通道数（默认1，单声道）
            device_name: 音频设备名称（None表示自动检测）
            device_index: 音频设备索引（备用参数）
        """
        self.ffmpeg_path = ffmpeg_path
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_name = device_name
        self.device_index = device_index
        
        self._validate_ffmpeg()
        
        if not self.device_name:
            self.device_name = self._auto_detect_device()
        
    def _validate_ffmpeg(self) -> None:
        """验证ffmpeg是否可用"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"ffmpeg验证成功")
            else:
                raise RuntimeError(f"ffmpeg验证失败: {result.stderr.decode()}")
        except FileNotFoundError:
            raise RuntimeError(f"ffmpeg未找到: {self.ffmpeg_path}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg验证超时")
    
    def _auto_detect_device(self) -> str:
        """
        自动检测音频输入设备
        
        Returns:
            设备名称
        """
        devices = self.list_audio_devices()
        
        for common_name in self.COMMON_DEVICE_NAMES:
            for device in devices:
                if common_name in device or device in common_name:
                    logger.info(f"自动检测到设备: {common_name}")
                    return common_name
        
        if devices:
            first_device = devices[0]
            if "audio=" in first_device:
                device_name = first_device.split("audio=")[1].strip()
            else:
                device_name = "麦克风"
            logger.info(f"使用首个设备: {device_name}")
            return device_name
        
        logger.warning("未检测到音频设备，使用默认名称: 麦克风")
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
            output_path: 输出文件路径（None表示使用临时文件）
            
        Returns:
            输出音频文件路径
        """
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".wav")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "dshow",
            "-i", f"audio={self.device_name}",
            "-acodec", "pcm_s16le",
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            "-t", str(duration),
            str(output_path)
        ]
        
        logger.info(f"开始录音: {duration}秒, 设备: {self.device_name}")
        logger.debug(f"ffmpeg命令: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=duration + 10
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                logger.error(f"录音失败: {error_msg}")
                raise RuntimeError(f"录音失败: {error_msg}")
            
            if not output_path.exists():
                raise RuntimeError("录音文件未生成")
            
            file_size = output_path.stat().st_size
            logger.info(f"录音完成: {output_path} ({file_size} bytes)")
            
            return str(output_path)
            
        except subprocess.TimeoutExpired:
            logger.error("录音超时")
            raise RuntimeError("录音超时")
        except Exception as e:
            logger.error(f"录音异常: {e}")
            raise
    
    def list_audio_devices(self) -> list:
        """
        列出可用的音频输入设备
        
        Returns:
            设备列表
        """
        cmd = [
            self.ffmpeg_path,
            "-list_devices", "true",
            "-f", "dshow",
            "-i", "dummy"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5
            )
            
            output = result.stderr.decode('utf-8', errors='ignore')
            devices = []
            
            for line in output.split('\n'):
                if 'audio' in line.lower():
                    devices.append(line.strip())
            
            logger.info(f"发现 {len(devices)} 个音频设备")
            return devices
            
        except Exception as e:
            logger.error(f"设备列表获取失败: {e}")
            return []
    
    def cleanup(self, audio_path: str) -> None:
        """清理临时音频文件"""
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"已清理临时文件: {audio_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")