"""
语音识别模块 - 使用适配器隔离外部依赖

改进：
- 使用WhisperAdapter替代直接whisper调用
- 使用OSAdapter替代直接os操作
- 使用LoggingAdapter替代直接logging
- 业务逻辑不依赖外部实现
"""

from typing import Optional, Any
from adapters import (
    AdapterFactory,
    IWhisperAdapter,
    IOSAdapter,
    ILoggingAdapter
)


class SpeechRecognizer:
    """语音识别器 - 使用适配器隔离依赖"""
    
    def __init__(
        self,
        model_size: str = "base",
        language: Optional[str] = "zh",
        temperature: float = 0.0,
        initial_prompt: str = "",
        whisper_adapter: Optional[IWhisperAdapter] = None,
        os_adapter: Optional[IOSAdapter] = None,
        logging_adapter: Optional[ILoggingAdapter] = None
    ):
        """
        初始化语音识别器
        
        Args:
            model_size: 模型大小
            language: 语言代码
            temperature: 采样温度
            initial_prompt: 初始提示
            whisper_adapter: Whisper适配器（测试时可注入mock）
            os_adapter: OS适配器（测试时可注入mock）
            logging_adapter: Logging适配器（测试时可注入mock）
        """
        self.model_size = model_size
        self.language = language
        self.temperature = temperature
        self.initial_prompt = initial_prompt
        
        self.whisper_adapter = whisper_adapter or AdapterFactory.create_whisper_adapter()
        self.os_adapter = os_adapter or AdapterFactory.create_os_adapter()
        self.logging_adapter = logging_adapter or AdapterFactory.create_logging_adapter()
        
        self.logger = self.logging_adapter.get_logger(__name__)
        
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """加载Whisper模型"""
        try:
            self.logger.info(f"加载Whisper模型: {self.model_size}")
            self.model = self.whisper_adapter.load_model(self.model_size)
            self.logger.info("Whisper模型加载成功")
        except Exception as e:
            self.logger.error(f"模型加载失败: {e}")
            raise RuntimeError(f"Whisper模型加载失败: {e}")
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> dict:
        """
        转录音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 语言代码
            
        Returns:
            转录结果字典
        """
        if not self.os_adapter.file_exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        lang = language or self.language
        
        self.logger.info(f"开始转录音频: {audio_path}")
        
        result = self.whisper_adapter.transcribe(
            model=self.model,
            audio_path=audio_path,
            language=lang,
            temperature=self.temperature,
            initial_prompt=self.initial_prompt
        )
        
        text = result.get('text', '')
        detected_lang = result.get('language', 'unknown')
        segments = result.get('segments', [])
        
        avg_confidence = 0.0
        if segments:
            confidences = [seg.get('avg_logprob', 0) for seg in segments]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        self.logger.info(f"转录完成: {text[:50]}...")
        self.logger.info(f"语言: {detected_lang}, 置信度: {avg_confidence:.2f}")
        
        return {
            'text': text,
            'language': detected_lang,
            'segments': segments,
            'confidence': avg_confidence
        }
    
    def transcribe_text_only(self, audio_path: str) -> str:
        """仅返回转录文本"""
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