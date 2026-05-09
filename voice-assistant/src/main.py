"""
主程序入口 - 整合所有模块实现语音控制opencode

功能：
- 加载配置
- 初始化所有模块
- 实现主循环
- 异常处理
- 日志记录
"""

import sys
import os
import logging
import signal
from pathlib import Path
from typing import Optional

import yaml

from audio_capture import AudioCapture
from speech_recognizer import SpeechRecognizer
from keyword_detector import KeywordDetector
from opencode_executor import OpenCodeExecutor

logger = logging.getLogger(__name__)


class VoiceAssistant:
    """语音助手主类"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初始化语音助手
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        
        self._setup_logging()
        
        self.audio_capture = None
        self.speech_recognizer = None
        self.keyword_detector = None
        self.opencode_executor = None
        
        self.running = False
        
        self._initialize_modules()
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            logger.warning(f"配置文件不存在: {config_file}")
            return self._get_default_config()
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"配置加载成功: {config_file}")
            return config
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            'audio': {
                'sample_rate': 16000,
                'channels': 1,
                'device_index': None,
                'segment_duration': 5
            },
            'whisper': {
                'model_size': 'base',
                'language': 'zh',
                'temperature': 0.0,
                'initial_prompt': ''
            },
            'opencode': {
                'executable': 'opencode',
                'timeout': 60,
                'auto_confirm': True
            },
            'keywords': [
                '创建', '读取', '编辑', '删除', '运行',
                '写代码', '搜索', '显示'
            ],
            'logging': {
                'voice_log': 'logs/voice.log',
                'command_log': 'logs/commands.log',
                'level': 'INFO',
                'max_size': 10485760,
                'backup_count': 5
            }
        }
    
    def _setup_logging(self) -> None:
        """设置日志"""
        log_config = self.config.get('logging', {})
        log_file = log_config.get('voice_log', 'logs/voice.log')
        log_level = log_config.get('level', 'INFO')
        
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        logger.info("日志系统初始化完成")
    
    def _initialize_modules(self) -> None:
        """初始化所有模块"""
        logger.info("初始化模块...")
        
        audio_config = self.config.get('audio', {})
        self.audio_capture = AudioCapture(
            sample_rate=audio_config.get('sample_rate', 16000),
            channels=audio_config.get('channels', 1),
            device_index=audio_config.get('device_index')
        )
        
        whisper_config = self.config.get('whisper', {})
        self.speech_recognizer = SpeechRecognizer(
            model_size=whisper_config.get('model_size', 'base'),
            language=whisper_config.get('language', 'zh'),
            temperature=whisper_config.get('temperature', 0.0),
            initial_prompt=whisper_config.get('initial_prompt', '')
        )
        
        keywords = self.config.get('keywords', [])
        self.keyword_detector = KeywordDetector(keywords=keywords)
        
        opencode_config = self.config.get('opencode', {})
        self.opencode_executor = OpenCodeExecutor(
            opencode_path=opencode_config.get('executable', 'opencode'),
            timeout=opencode_config.get('timeout', 60),
            auto_confirm=opencode_config.get('auto_confirm', True),
            workdir=str(Path.cwd())
        )
        
        logger.info("所有模块初始化完成")
    
    def _signal_handler(self, signum, frame) -> None:
        """信号处理器"""
        logger.info(f"收到信号 {signum}，准备退出...")
        self.running = False
    
    def process_segment(self, duration: Optional[float] = None) -> Optional[dict]:
        """
        处理一个语音段
        
        Args:
            duration: 录音时长（秒）
            
        Returns:
            处理结果
        """
        if duration is None:
            duration = self.config.get('audio', {}).get('segment_duration', 5)
        
        try:
            logger.info(f"开始录音（{duration}秒）...")
            audio_file = self.audio_capture.record_segment(duration=duration)
            
            logger.info("开始语音识别...")
            transcription = self.speech_recognizer.transcribe(audio_file)
            text = transcription['text']
            
            if not text:
                logger.info("未检测到语音")
                self.audio_capture.cleanup(audio_file)
                return None
            
            logger.info(f"识别结果: {text}")
            
            detected, keyword, param = self.keyword_detector.detect(text)
            
            if not detected:
                logger.info("未检测到关键词")
                self.audio_capture.cleanup(audio_file)
                return {
                    'text': text,
                    'detected': False,
                    'executed': False
                }
            
            if not self.keyword_detector.is_valid_command(keyword, param):
                logger.warning(f"命令验证失败: {keyword} {param}")
                self.audio_capture.cleanup(audio_file)
                return {
                    'text': text,
                    'detected': True,
                    'executed': False,
                    'error': '命令验证失败'
                }
            
            command = self.keyword_detector.format_command(keyword, param)
            logger.info(f"执行命令: {command}")
            
            log_file = self.config.get('logging', {}).get('command_log', 'logs/commands.log')
            result = self.opencode_executor.execute_and_log(command, log_file=log_file)
            
            self.audio_capture.cleanup(audio_file)
            
            return {
                'text': text,
                'detected': True,
                'executed': result['success'],
                'keyword': keyword,
                'param': param,
                'command': command,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"处理失败: {e}")
            return {
                'text': '',
                'detected': False,
                'executed': False,
                'error': str(e)
            }
    
    def run(self) -> None:
        """运行主循环"""
        logger.info("="*60)
        logger.info("语音助手启动")
        logger.info("="*60)
        logger.info("等待语音输入... (按Ctrl+C退出)")
        logger.info("")
        
        self.running = True
        
        while self.running:
            try:
                result = self.process_segment()
                
                if result and result.get('detected'):
                    if result.get('executed'):
                        logger.info("✓ 命令执行成功")
                    else:
                        logger.warning("✗ 命令执行失败")
                
            except KeyboardInterrupt:
                logger.info("用户中断")
                break
            except Exception as e:
                logger.error(f"主循环异常: {e}")
                continue
        
        logger.info("="*60)
        logger.info("语音助手停止")
        logger.info("="*60)
    
    def run_once(self, duration: Optional[float] = None) -> dict:
        """
        运行一次语音处理
        
        Args:
            duration: 录音时长
            
        Returns:
            处理结果
        """
        return self.process_segment(duration=duration)


def main():
    """主函数"""
    config_path = os.environ.get('VOICE_ASSISTANT_CONFIG', 'config/config.yaml')
    
    try:
        assistant = VoiceAssistant(config_path=config_path)
        assistant.run()
    except Exception as e:
        logger.error(f"启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()