"""
语音识别模块 - 使用Whisper进行语音转文字

功能：
- 本地Whisper模型加载
- 音频文件转文字
- 支持多种模型大小
- 自动语言检测
"""

import logging
from typing import Optional
from pathlib import Path

import whisper

logger = logging.getLogger(__name__)


class SpeechRecognizer:
    """语音识别器 - 使用Whisper进行语音转文字"""
    
    def __init__(
        self,
        model_size: str = "base",
        language: Optional[str] = "zh",
        temperature: float = 0.0,
        initial_prompt: str = ""
    ):
        """
        初始化语音识别器
        
        Args:
            model_size: 模型大小（tiny/base/small/medium/large）
            language: 语言代码（zh=中文，None=自动检测）
            temperature: 采样温度（0.0=确定性输出）
            initial_prompt: 初始提示（帮助模型理解上下文）
        """
        self.model_size = model_size
        self.language = language
        self.temperature = temperature
        self.initial_prompt = initial_prompt
        
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """加载Whisper模型"""
        try:
            logger.info(f"加载Whisper模型: {self.model_size}")
            self.model = whisper.load_model(self.model_size)
            logger.info("Whisper模型加载成功")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise RuntimeError(f"Whisper模型加载失败: {e}")
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> dict:
        """
        转录音频文件
        
        Args:
            audio_path: 音频文件路径（WAV格式）
            language: 语言代码（覆盖默认设置）
            
        Returns:
            转录结果字典：
            {
                'text': str,          # 识别文本
                'language': str,      # 检测到的语言
                'segments': list,     # 时间分段
                'confidence': float   # 置信度
            }
        """
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        lang = language or self.language
        
        logger.info(f"开始转录音频: {audio_path}")
        logger.debug(f"语言设置: {lang or '自动检测'}")
        
        try:
            result = self.model.transcribe(
                audio_path,
                language=lang,
                temperature=self.temperature,
                initial_prompt=self.initial_prompt,
                verbose=False
            )
            
            text = result.get('text', '').strip()
            detected_lang = result.get('language', 'unknown')
            segments = result.get('segments', [])
            
            avg_confidence = 0.0
            if segments:
                confidences = [seg.get('avg_logprob', 0) for seg in segments]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            transcription = {
                'text': text,
                'language': detected_lang,
                'segments': segments,
                'confidence': avg_confidence
            }
            
            logger.info(f"转录完成: {text[:50]}...")
            logger.info(f"语言: {detected_lang}, 置信度: {avg_confidence:.2f}")
            
            return transcription
            
        except Exception as e:
            logger.error(f"转录失败: {e}")
            raise RuntimeError(f"转录失败: {e}")
    
    def transcribe_text_only(self, audio_path: str) -> str:
        """
        仅返回转录文本（简化接口）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录文本
        """
        result = self.transcribe(audio_path)
        return result['text']
    
    def get_model_info(self) -> dict:
        """获取模型信息"""
        return {
            'model_size': self.model_size,
            'language': self.language or 'auto',
            'temperature': self.temperature,
            'device': str(self.model.device) if hasattr(self.model, 'device') else 'unknown'
        }