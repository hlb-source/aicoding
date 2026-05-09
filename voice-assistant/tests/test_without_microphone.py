"""
测试脚本 - 无需麦克风输入，测试核心功能

测试内容：
- 模块初始化
- Whisper模型加载
- 关键词检测
- 日志记录
"""

import sys
import os
from pathlib import Path

os.environ['PYTHONIOENCODING'] = 'utf-8'

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adapters import AdapterFactory
from keyword_detector import KeywordDetector
from speech_recognizer import SpeechRecognizer
from opencode_executor import OpenCodeExecutor


def test_modules():
    """测试各模块初始化"""
    print("\n" + "="*60)
    print("语音助手模块测试（无需麦克风）")
    print("="*60)
    
    print("\n1. 测试适配器工厂...")
    try:
        subprocess_adapter = AdapterFactory.create_subprocess_adapter()
        print("[OK] SubprocessAdapter创建成功")
        
        yaml_adapter = AdapterFactory.create_yaml_adapter()
        print("[OK] YAMLAdapter创建成功")
        
        os_adapter = AdapterFactory.create_os_adapter()
        print("[OK] OSAdapter创建成功")
        
        logging_adapter = AdapterFactory.create_logging_adapter()
        print("[OK] LoggingAdapter创建成功")
        
    except Exception as e:
        print(f"[FAIL] 适配器创建失败: {e}")
        return False
    
    print("\n2. 测试关键词检测器...")
    try:
        detector = KeywordDetector()
        
        test_texts = [
            "创建文件 main.py",
            "读取文件 app.py",
            "运行测试",
        ]
        
        for text in test_texts:
            detected, keyword, param = detector.detect(text)
            if detected:
                category = detector.get_keyword_category(keyword)
                print(f"[OK] 检测到: {keyword} ({category}), 参数: {param}")
            else:
                print(f"[WARN] 未检测到关键词: {text}")
        
        print("[OK] 关键词检测器工作正常")
        
    except Exception as e:
        print(f"[FAIL] 关键词检测器失败: {e}")
        return False
    
    print("\n3. 测试Whisper模型加载...")
    try:
        recognizer = SpeechRecognizer(model_size="base", language="zh")
        info = recognizer.get_model_info()
        
        print(f"[OK] Whisper模型加载成功")
        print(f"  模型大小: {info['model_size']}")
        print(f"  语言: {info['language']}")
        print(f"  设备: {info['device']}")
        
    except Exception as e:
        print(f"[FAIL] Whisper模型加载失败: {e}")
        return False
    
    print("\n4. 测试opencode执行器...")
    try:
        executor = OpenCodeExecutor(timeout=10)
        
        result = executor.execute("--version")
        
        if result['success']:
            print("[OK] opencode执行器工作正常")
            print(f"  版本: {result['output'][:50]}")
        else:
            print(f"[WARN] opencode执行失败: {result['error']}")
            print("  提示: 可能需要配置正确的opencode路径")
        
    except Exception as e:
        print(f"[FAIL] opencode执行器失败: {e}")
    
    print("\n5. 测试日志记录...")
    try:
        logger = logging_adapter.get_logger("test")
        logger.info("="*60)
        logger.info("【测试日志记录】")
        logger.info("  时间: 2026-05-09")
        logger.info("  状态: 正常")
        logger.info("="*60)
        
        print("[OK] 日志记录正常")
        
    except Exception as e:
        print(f"[FAIL] 日志记录失败: {e}")
        return False
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    
    return True


def test_keyword_detection():
    """测试关键词检测功能"""
    print("\n" + "="*60)
    print("关键词检测功能测试")
    print("="*60)
    
    detector = KeywordDetector()
    
    print("\n关键词列表:")
    for category, keywords in detector.keyword_groups.items():
        print(f"  {category}: {keywords}")
    
    print("\n测试案例:")
    test_cases = [
        ("创建文件 main.py", "创建", "文件 main.py"),
        ("新建项目 myproject", "新建", "项目 myproject"),
        ("读取文件 config.yaml", "读取", "文件 config.yaml"),
        ("打开文件 app.py", "打开", "文件 app.py"),
        ("编辑文件 test.py", "编辑", "文件 test.py"),
        ("修改文件 data.txt", "修改", "文件 data.txt"),
        ("删除文件 old.py", "删除", "文件 old.py"),
        ("运行测试", "运行", "测试"),
        ("执行命令", "执行", "命令"),
        ("写代码实现功能", "写代码", "实现功能"),
        ("搜索文件 test", "搜索", "文件 test"),
        ("测试模块", "测试", "模块"),
    ]
    
    passed = 0
    for text, expected_keyword, expected_param in test_cases:
        detected, keyword, param = detector.detect(text)
        
        if detected and keyword == expected_keyword:
            category = detector.get_keyword_category(keyword)
            print(f"[OK] '{text}' -> {keyword}({category}) + {param}")
            passed += 1
        else:
            print(f"[FAIL] '{text}' -> 未检测到或关键词错误")
    
    print(f"\n测试通过率: {passed}/{len(test_cases)}")
    
    return passed == len(test_cases)


if __name__ == "__main__":
    success = test_modules()
    
    if success:
        test_keyword_detection()
    
    print("\n提示:")
    print("  - 语音助手核心功能已测试")
    print("  - 要运行完整语音助手，需要连接真实麦克风")
    print("  - 运行完整助手: python src/main.py")
    print("="*60)