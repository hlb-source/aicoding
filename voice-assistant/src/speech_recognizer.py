"""
语音识别模块 - 使用适配器隔离外部依赖

改进：
- 使用WhisperAdapter替代直接whisper调用
- 使用OSAdapter替代直接os操作
- 使用LoggingAdapter替代直接logging
- 业务逻辑不依赖外部实现
- 确保输出简体中文格式
"""

from typing import Optional, Any
from adapters import (
    AdapterFactory,
    IWhisperAdapter,
    IOSAdapter,
    ILoggingAdapter
)


def to_simplified_chinese(text: str) -> str:
    """
    转换繁体中文到简体中文
    
    Args:
        text: 输入文本
        
    Returns:
        简体中文文本
    """
    # 常见繁简对照表
    traditional_to_simplified = {
        '作': '作',
        '词': '词',
        '曲': '曲',
        '啊': '啊',
        '的': '的',
        '是': '是',
        '在': '在',
        '有': '有',
        '和': '和',
        '与': '与',
        '或': '或',
        '不': '不',
        '要': '要',
        '能': '能',
        '会': '会',
        '说': '说',
        '听': '听',
        '看': '看',
        '想': '想',
        '做': '做',
        '来': '来',
        '去': '去',
        '上': '上',
        '下': '下',
        '左': '左',
        '右': '右',
        '前': '前',
        '后': '后',
        '里': '里',
        '外': '外',
        '中': '中',
        '大': '大',
        '小': '小',
        '多': '多',
        '少': '少',
        '好': '好',
        '坏': '坏',
        '对': '对',
        '错': '错',
        '真': '真',
        '假': '假',
        '新': '新',
        '旧': '旧',
        '生': '生',
        '死': '死',
        '開': '开',
        '關': '关',
        '創': '创',
        '建': '建',
        '讀': '读',
        '取': '取',
        '寫': '写',
        '編': '编',
        '輯': '辑',
        '删': '删',
        '除': '除',
        '運': '运',
        '行': '行',
        '執': '执',
        '啟': '启',
        '動': '动',
        '搜': '搜',
        '尋': '寻',
        '找': '找',
        '顯': '显',
        '示': '示',
        '列': '列',
        '測': '测',
        '試': '试',
        '調': '调',
        '檔': '档',
        '案': '案',
        '文': '文',
        '件': '件',
        '目': '目',
        '錄': '录',
    }
    
    result = []
    for char in text:
        if char in traditional_to_simplified:
            result.append(traditional_to_simplified[char])
        else:
            result.append(char)
    
    return ''.join(result)


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
        import traceback
        
        if not self.os_adapter.file_exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        lang = language or self.language
        
        self.logger.info(f"开始转录音频: {audio_path}")
        self.logger.info(f"音频文件存在: {self.os_adapter.file_exists(audio_path)}")
        self.logger.info(f"音频文件大小: {self.os_adapter.get_file_size(audio_path)}")
        
        try:
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
            
            # 转换为简体中文
            text = to_simplified_chinese(text)
            
            avg_confidence = 0.0
            if segments:
                confidences = [seg.get('avg_logprob', 0) for seg in segments]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            self.logger.info(f"转录完成: {text[:50]}...")
            self.logger.info(f"语言: {detected_lang}, 置信度: {avg_confidence:.2f}")
            self.logger.info(f"已转换为简体中文格式")
            
            return {
                'text': text,
                'language': detected_lang,
                'segments': segments,
                'confidence': avg_confidence
            }
            
        except Exception as e:
            error_traceback = traceback.format_exc()
            self.logger.error(f"转录异常: {e}")
            self.logger.error(f"错误堆栈:\n{error_traceback}")
            raise RuntimeError(f"转录失败: {e}\n{error_traceback}")
    
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