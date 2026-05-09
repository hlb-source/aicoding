"""
测试脚本 - 测试各个模块功能

测试内容：
- 配置加载
- 音频设备检测
- Whisper模型加载
- 关键词检测
- opencode调用
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_config_loading():
    """测试配置加载"""
    print("\n" + "="*60)
    print("测试1: 配置加载")
    print("="*60)
    
    try:
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        print("✓ 配置加载成功")
        print(f"  - 音频采样率: {config['audio']['sample_rate']}")
        print(f"  - Whisper模型: {config['whisper']['model_size']}")
        print(f"  - 关键词数量: {len(config['keywords'])}")
        return True
        
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        return False


def test_keyword_detector():
    """测试关键词检测"""
    print("\n" + "="*60)
    print("测试2: 关键词检测")
    print("="*60)
    
    try:
        from keyword_detector import KeywordDetector
        
        detector = KeywordDetector()
        
        test_cases = [
            ("创建文件 main.py", True, "创建", "main.py"),
            ("读取文件 app.py", True, "读取", "app.py"),
            ("运行测试", True, "运行", "测试"),
            ("今天天气不错", False, None, None),
            ("写代码实现功能", True, "写代码", "实现功能"),
        ]
        
        all_passed = True
        for text, should_detect, expected_keyword, expected_param in test_cases:
            detected, keyword, param = detector.detect(text)
            
            if detected == should_detect:
                status = "✓"
            else:
                status = "✗"
                all_passed = False
            
            print(f"{status} 文本: '{text}'")
            print(f"   检测: {detected}, 关键词: {keyword}, 参数: {param}")
        
        return all_passed
        
    except Exception as e:
        print(f"✗ 关键词检测测试失败: {e}")
        return False


def test_opencode_executor():
    """测试opencode执行器"""
    print("\n" + "="*60)
    print("测试3: opencode执行器")
    print("="*60)
    
    try:
        from opencode_executor import OpenCodeExecutor
        
        executor = OpenCodeExecutor(timeout=10)
        
        print("执行测试命令: --version")
        result = executor.execute("--version")
        
        if result['success']:
            print("✓ opencode执行成功")
            print(f"  版本信息: {result['output'][:50]}...")
            return True
        else:
            print("✗ opencode执行失败")
            print(f"  错误: {result['error']}")
            return False
            
    except Exception as e:
        print(f"✗ opencode测试失败: {e}")
        return False


def test_audio_devices():
    """测试音频设备检测"""
    print("\n" + "="*60)
    print("测试4: 音频设备检测")
    print("="*60)
    
    try:
        from audio_capture import AudioCapture
        
        capture = AudioCapture()
        devices = capture.list_audio_devices()
        
        if devices:
            print(f"✓ 发现 {len(devices)} 个音频设备")
            for device in devices[:3]:
                print(f"  - {device[:60]}...")
            return True
        else:
            print("⚠ 未发现音频设备（可能需要手动配置）")
            return True
            
    except Exception as e:
        print(f"✗ 音频设备检测失败: {e}")
        return False


def test_whisper_loading():
    """测试Whisper模型加载"""
    print("\n" + "="*60)
    print("测试5: Whisper模型加载")
    print("="*60)
    
    try:
        from speech_recognizer import SpeechRecognizer
        
        print("加载Whisper base模型（首次需要下载约74MB）...")
        recognizer = SpeechRecognizer(model_size="base", language="zh")
        
        info = recognizer.get_model_info()
        print("✓ Whisper模型加载成功")
        print(f"  - 模型大小: {info['model_size']}")
        print(f"  - 语言: {info['language']}")
        print(f"  - 设备: {info['device']}")
        return True
        
    except Exception as e:
        print(f"✗ Whisper模型加载失败: {e}")
        print("  提示: 首次运行需要下载模型文件")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("语音助手模块测试")
    print("="*60)
    
    tests = [
        ("配置加载", test_config_loading),
        ("关键词检测", test_keyword_detector),
        ("opencode执行器", test_opencode_executor),
        ("音频设备检测", test_audio_devices),
        ("Whisper模型加载", test_whisper_loading),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ 测试异常: {name} - {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    print("="*60)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)