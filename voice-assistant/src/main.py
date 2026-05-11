"""
主程序入口 - 使用适配器隔离所有外部依赖

改进：
- 所有外部依赖通过适配器访问
- 业务逻辑完全不依赖外部实现
- 方便测试时注入mock/stub
"""

import sys
from typing import Optional
from adapters import (
    AdapterFactory,
    IYAMLAdapter,
    IOSAdapter,
    ILoggingAdapter,
    ISignalAdapter
)

from audio_capture import AudioCapture
from speech_recognizer import SpeechRecognizer
from keyword_detector import KeywordDetector


class VoiceAssistant:
    """语音助手主类 - 使用适配器隔离依赖"""
    
    def __init__(
        self,
        config_path: str = "config/config.yaml",
        yaml_adapter: Optional[IYAMLAdapter] = None,
        os_adapter: Optional[IOSAdapter] = None,
        logging_adapter: Optional[ILoggingAdapter] = None,
        signal_adapter: Optional[ISignalAdapter] = None
    ):
        """
        初始化语音助手
        
        Args:
            config_path: 配置文件路径
            yaml_adapter: YAML适配器（测试时可注入mock）
            os_adapter: OS适配器（测试时可注入mock）
            logging_adapter: Logging适配器（测试时可注入mock）
            signal_adapter: Signal适配器（测试时可注入mock）
        """
        self.config_path = config_path
        
        self.yaml_adapter = yaml_adapter or AdapterFactory.create_yaml_adapter()
        self.os_adapter = os_adapter or AdapterFactory.create_os_adapter()
        self.logging_adapter = logging_adapter or AdapterFactory.create_logging_adapter()
        self.signal_adapter = signal_adapter or AdapterFactory.create_signal_adapter()
        
        self.config = self._load_config()
        self._setup_logging()
        
        self.logger = self.logging_adapter.get_logger(__name__)
        
        self.audio_capture = None
        self.speech_recognizer = None
        self.keyword_detector = None
        
        self.running = False
        
        self._initialize_modules()
        
        self.signal_adapter.register_handler(2, self._signal_handler)
        self.signal_adapter.register_handler(15, self._signal_handler)
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        config = self.yaml_adapter.load(self.config_path)
        
        if not config:
            self.logging_adapter.get_logger(__name__).warning(
                f"配置文件不存在或为空: {self.config_path}"
            )
            return self._get_default_config()
        
        return config
    
    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            'audio': {
                'sample_rate': 16000,
                'channels': 1,
                'device_name': '麦克风',
                'segment_duration': 2,
                'archive_enabled': False,
                'archive_dir': 'logs/audio_archive'
            },
            'whisper': {
                'model_size': 'tiny',
                'language': 'zh',
                'temperature': 0.0,
                'initial_prompt': ''
            },
            'keywords': KeywordDetector.DEFAULT_KEYWORDS,
            'logging': {
                'voice_log': 'logs/voice.log',
                'command_log': 'logs/commands.log',
                'level': 'INFO'
            }
        }
    
    def _setup_logging(self) -> None:
        """设置日志"""
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        
        # 输出到console和console.log文件
        # voice.log专门用于记录语音输入文本
        self.logging_adapter.setup(log_file='logs/console.log', level=log_level)
    
    def _initialize_modules(self) -> None:
        """初始化所有模块"""
        self.logger.info("初始化模块...")
        
        audio_config = self.config.get('audio', {})
        self.audio_capture = AudioCapture(
            ffmpeg_path=self.config.get('ffmpeg_path', 'ffmpeg'),
            sample_rate=audio_config.get('sample_rate', 16000),
            channels=audio_config.get('channels', 1),
            device_name=audio_config.get('device_name', '麦克风'),
            archive_enabled=audio_config.get('archive_enabled', False),
            archive_dir=audio_config.get('archive_dir', 'logs/audio_archive')
        )
        
        whisper_config = self.config.get('whisper', {})
        self.speech_recognizer = SpeechRecognizer(
            model_size=whisper_config.get('model_size', 'base'),
            language=whisper_config.get('language', 'zh'),
            temperature=whisper_config.get('temperature', 0.0),
            initial_prompt=whisper_config.get('initial_prompt', '')
        )
        
        keywords = self.config.get('keywords', KeywordDetector.DEFAULT_KEYWORDS)
        self.keyword_detector = KeywordDetector(keywords=keywords)
        
        self.logger.info("所有模块初始化完成")
    
    def _signal_handler(self, signum, frame) -> None:
        """信号处理器"""
        self.logger.info(f"收到信号 {signum}，准备退出...")
        self.running = False
    
    def _log_voice_input(
        self,
        log_file: str,
        text: str,
        language: str,
        confidence: float,
        status: str
    ) -> None:
        """
        记录麦克风输入到日志文件
        
        Args:
            log_file: 日志文件路径
            text: 识别文本
            language: 语言
            confidence: 置信度
            status: 状态
        """
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 只记录语音输入内容，简洁格式
        if text:
            log_content = f"[{timestamp}] {text}\n"
        else:
            log_content = f"[{timestamp}] (无语音输入)\n"
        
        self.os_adapter.write_file(log_file, log_content, mode='a', encoding='utf-8')
    
    def _log_command(
        self,
        log_file: str,
        command: str,
        keyword: str,
        param: str,
        text: str
    ) -> None:
        """
        记录语音命令到日志文件
        
        Args:
            log_file: 日志文件路径
            command: 格式化命令
            keyword: 关键词
            param: 参数
            text: 原始文本
        """
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_content = "\n" + "="*60 + "\n"
        log_content += f"[{timestamp}] 语音命令\n"
        log_content += "="*60 + "\n"
        log_content += f"原始文本: {text}\n"
        log_content += f"关键词: {keyword}\n"
        log_content += f"参数: {param}\n"
        log_content += f"命令内容: {command}\n"
        log_content += f"执行状态: 待执行（已记录）\n"
        log_content += "="*60 + "\n"
        
        self.os_adapter.write_file(log_file, log_content, mode='a', encoding='utf-8')
        self.logger.info(f"命令已写入日志: {log_file}")
    
    def process_segment(self, duration: Optional[float] = None) -> Optional[dict]:
        """处理一个语音段"""
        from datetime import datetime
        
        if duration is None:
            duration = self.config.get('audio', {}).get('segment_duration', 5)
        
        process_start_time = datetime.now()
        audio_file = None
        
        try:
            self.logger.info("【语音处理流程开始】")
            self.logger.info(f"录音时长: {duration}秒")
            
            audio_file = self.audio_capture.record_segment(duration=duration)
            
            transcription = self.speech_recognizer.transcribe(audio_file)
            text = transcription['text']
            language = transcription.get('language', 'unknown')
            confidence = transcription.get('confidence', 0.0)
            
            if not text:
                voice_log_file = self.config.get('logging', {}).get('voice_log', 'logs/voice.log')
                self._log_voice_input(
                    log_file=voice_log_file,
                    text="",
                    language=language,
                    confidence=confidence,
                    status="无语音"
                )
                
                return None
            
            self.logger.info(f"识别结果: {text}")
            
            voice_log_file = self.config.get('logging', {}).get('voice_log', 'logs/voice.log')
            self._log_voice_input(
                log_file=voice_log_file,
                text=text,
                language=language,
                confidence=confidence,
                status="已识别"
            )
            
            detected, keyword, param = self.keyword_detector.detect(text)
            
            if not detected:
                self.logger.info(f"未检测到关键词")
                
                return {
                    'text': text,
                    'detected': False,
                    'executed': False
                }
            
            category = self.keyword_detector.get_keyword_category(keyword)
            
            self.logger.info(f"检测到关键词: {keyword} ({category})")
            
            if not self.keyword_detector.is_valid_command(keyword, param):
                self.logger.warning(f"命令验证失败: {keyword} {param}")
                
                return {
                    'text': text,
                    'detected': True,
                    'executed': False,
                    'error': '命令验证失败'
                }
            
            command = self.keyword_detector.format_command(keyword, param)
            
            self.logger.info(f"语音命令: {command}")
            
            # 将命令写入日志文件，不执行opencode
            command_log_file = self.config.get('logging', {}).get('command_log', 'logs/commands.log')
            self._log_command(
                log_file=command_log_file,
                command=command,
                keyword=keyword,
                param=param,
                text=text
            )
            
            # 打印到console
            print(f"[命令] {command}")
            
            return {
                'text': text,
                'detected': True,
                'executed': False,
                'keyword': keyword,
                'param': param,
                'command': command,
                'result': None
            }
            
        except Exception as e:
            self.logger.error("="*60)
            self.logger.error("【语音处理流程异常】")
            self.logger.error(f"  异常时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.error(f"  异常信息: {e}")
            self.logger.error("="*60)
            
            return {
                'text': '',
                'detected': False,
                'executed': False,
                'error': str(e)
            }
        
        finally:
            if audio_file:
                archive_path = self.audio_capture.cleanup(audio_file, archive=True)
                if archive_path:
                    self.logger.info(f"录音已归档: {archive_path}")
                else:
                    self.logger.info("临时文件已清理")
    
    def run(self) -> None:
        """运行主循环"""
        self.logger.info("="*60)
        self.logger.info("语音助手启动")
        self.logger.info("="*60)
        self.logger.info("等待语音输入... (按Ctrl+C退出)")
        
        self.running = True
        
        while self.running:
            try:
                result = self.process_segment()
                
                if result and result.get('detected'):
                    if result.get('executed'):
                        self.logger.info("✓ 命令执行成功")
                    else:
                        self.logger.warning("✗ 命令执行失败")
                
            except KeyboardInterrupt:
                self.logger.info("用户中断")
                break
            except Exception as e:
                self.logger.error(f"主循环异常: {e}")
                continue
        
        self.logger.info("="*60)
        self.logger.info("语音助手停止")
        self.logger.info("="*60)
    
    def run_once(self, duration: Optional[float] = None) -> dict:
        """运行一次语音处理"""
        return self.process_segment(duration=duration)


def main():
    """主函数"""
    import os
    
    # Windows UTF-8 encoding fix
    if sys.platform == 'win32':
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    
    config_path = os.environ.get('VOICE_ASSISTANT_CONFIG', 'config/config.yaml')
    
    try:
        assistant = VoiceAssistant(config_path=config_path)
        assistant.run()
    except Exception as e:
        AdapterFactory.create_logging_adapter().get_logger(__name__).error(f"启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()