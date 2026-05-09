"""
Whisper适配器 - 隔离Whisper依赖

功能：
- 封装whisper.load_model()
- 封装model.transcribe()
- 提供统一返回格式
"""

import whisper
from typing import Any, Dict, Optional


class WhisperAdapter:
    """Whisper适配器实现"""
    
    def load_model(self, model_size: str) -> Any:
        """
        加载Whisper模型
        
        Args:
            model_size: 模型大小
            
        Returns:
            模型对象
        """
        return whisper.load_model(model_size)
    
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
        result = model.transcribe(
            audio_path,
            language=language,
            temperature=temperature,
            initial_prompt=initial_prompt,
            verbose=False,
            fp16=False
        )
        
        return {
            'text': result.get('text', '').strip(),
            'language': result.get('language', 'unknown'),
            'segments': result.get('segments', [])
        }