"""
使用示例脚本 - 演示语音助手基本用法

演示内容：
- 单次语音识别
- 关键词检测
- opencode命令执行
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audio_capture import AudioCapture
from speech_recognizer import SpeechRecognizer
from keyword_detector import KeywordDetector
from opencode_executor import OpenCodeExecutor


def example_single_recognition():
    """示例1: 单次语音识别"""
    print("\n" + "="*60)
    print("示例1: 单次语音识别（5秒录音）")
    print("="*60)
    
    try:
        print("\n初始化音频采集器...")
        audio = AudioCapture(ffmpeg_path="D:\\code\\aicoding\\ffmpeg\\bin\\ffmpeg.exe")
        
        print("\n初始化语音识别器...")
        recognizer = SpeechRecognizer(model_size="base", language="zh")
        
        print("\n开始录音（请说话）...")
        audio_file = audio.record_segment(duration=5)
        
        print("\n识别音频...")
        result = recognizer.transcribe(audio_file)
        
        print(f"\n识别结果: {result['text']}")
        print(f"语言: {result['language']}")
        
        audio.cleanup(audio_file)
        
    except Exception as e:
        print(f"\n示例失败: {e}")


def example_keyword_detection():
    """示例2: 关键词检测"""
    print("\n" + "="*60)
    print("示例2: 关键词检测")
    print("="*60)
    
    detector = KeywordDetector()
    
    test_texts = [
        "创建文件 main.py",
        "读取文件 app.py",
        "运行测试",
        "写代码实现功能",
        "今天天气不错",
    ]
    
    print("\n关键词列表:", detector.get_keywords())
    
    for text in test_texts:
        detected, keyword, param = detector.detect(text)
        status = "✓ 检测到" if detected else "✗ 未检测到"
        print(f"\n{status} 文本: '{text}'")
        if detected:
            print(f"  关键词: {keyword}")
            print(f"  参数: {param}")
            print(f"  类别: {detector.get_keyword_category(keyword)}")


def example_opencode_execution():
    """示例3: opencode命令执行"""
    print("\n" + "="*60)
    print("示例3: opencode命令执行")
    print("="*60)
    
    try:
        executor = OpenCodeExecutor(timeout=10)
        
        print("\n执行测试命令: --version")
        result = executor.execute("--version")
        
        if result['success']:
            print(f"\n✓ 执行成功")
            print(f"输出: {result['output'][:100]}...")
        else:
            print(f"\n✗ 执行失败")
            print(f"错误: {result['error']}")
            
    except Exception as e:
        print(f"\n示例失败: {e}")


def example_full_workflow():
    """示例4: 完整工作流程"""
    print("\n" + "="*60)
    print("示例4: 完整工作流程（语音→识别→检测→执行）")
    print("="*60)
    
    print("\n提示：此示例需要麦克风输入")
    print("是否继续？(y/n): ")
    
    choice = input().strip().lower()
    if choice != 'y':
        print("\n跳过完整流程示例")
        return
    
    try:
        print("\n初始化模块...")
        audio = AudioCapture(ffmpeg_path="D:\\code\\aicoding\\ffmpeg\\bin\\ffmpeg.exe")
        recognizer = SpeechRecognizer(model_size="base", language="zh")
        detector = KeywordDetector()
        executor = OpenCodeExecutor(timeout=60)
        
        print("\n开始录音（5秒，请说出命令）...")
        audio_file = audio.record_segment(duration=5)
        
        print("\n识别语音...")
        result = recognizer.transcribe(audio_file)
        text = result['text']
        
        print(f"\n识别文本: {text}")
        
        detected, keyword, param = detector.detect(text)
        
        if detected:
            print(f"\n✓ 检测到关键词: {keyword}")
            
            if detector.is_valid_command(keyword, param):
                command = detector.format_command(keyword, param)
                print(f"\n执行命令: {command}")
                
                exec_result = executor.execute_and_log(command)
                
                if exec_result['success']:
                    print("\n✓ 命令执行成功")
                else:
                    print("\n✗ 命令执行失败")
                    print(f"错误: {exec_result['error']}")
            else:
                print("\n✗ 命令验证失败")
        else:
            print("\n✗ 未检测到关键词")
        
        audio.cleanup(audio_file)
        
    except Exception as e:
        print(f"\n示例失败: {e}")


def main():
    """运行所有示例"""
    print("\n" + "="*60)
    print("语音助手使用示例")
    print("="*60)
    
    examples = [
        ("单次语音识别", example_single_recognition),
        ("关键词检测", example_keyword_detection),
        ("opencode命令执行", example_opencode_execution),
        ("完整工作流程", example_full_workflow),
    ]
    
    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"\n示例 '{name}' 失败: {e}")
    
    print("\n" + "="*60)
    print("示例演示完成")
    print("="*60)


if __name__ == "__main__":
    main()