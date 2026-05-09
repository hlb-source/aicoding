"""
设备配置助手 - 帮助用户配置音频设备

功能：
- 检测音频输入设备
- 测试录音功能
- 生成配置文件
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml
from audio_capture import AudioCapture


def check_audio_devices():
    """检查音频输入设备"""
    print("\n" + "="*60)
    print("音频设备检测")
    print("="*60)
    
    try:
        audio = AudioCapture(ffmpeg_path="D:\\code\\aicoding\\ffmpeg\\bin\\ffmpeg.exe")
        devices = audio.list_audio_devices()
        
        if devices:
            print(f"\n✓ 发现 {len(devices)} 个音频设备")
            for i, device in enumerate(devices, 1):
                print(f"\n{i}. {device}")
            
            print("\n" + "-"*60)
            print("建议：选择包含'麦克风'或'Microphone'的设备")
            print("-"*60)
            
            return devices
        else:
            print("\n✗ 未发现音频设备")
            print("\n可能原因：")
            print("  1. 没有连接麦克风")
            print("  2. 麦克风被禁用")
            print("  3. ffmpeg dshow驱动问题")
            print("\n解决方法：")
            print("  1. 检查Windows设置 → 系统 → 声音 → 输入")
            print("  2. 确保麦克风已启用")
            print("  3. 尝试重启ffmpeg服务")
            return []
            
    except Exception as e:
        print(f"\n✗ 设备检测失败: {e}")
        print("\n请检查ffmpeg是否正确安装")
        return []


def test_recording(device_name: str = "麦克风", duration: int = 3):
    """测试录音功能"""
    print("\n" + "="*60)
    print("录音测试")
    print("="*60)
    
    try:
        print(f"\n使用设备: {device_name}")
        print(f"录音时长: {duration}秒")
        
        audio = AudioCapture(
            ffmpeg_path="D:\\code\\aicoding\\ffmpeg\\bin\\ffmpeg.exe",
            device_name=device_name
        )
        
        print("\n开始录音（请说话）...")
        audio_file = audio.record_segment(duration=duration)
        
        print(f"\n✓ 录音成功: {audio_file}")
        
        file_size = Path(audio_file).stat().st_size
        print(f"文件大小: {file_size} bytes")
        
        if file_size < 1000:
            print("\n⚠ 文件太小，可能没有录制到声音")
            print("请检查麦克风是否正常工作")
        else:
            print("\n✓ 录音文件正常")
        
        audio.cleanup(audio_file)
        
        return True
        
    except Exception as e:
        print(f"\n✗ 录音测试失败: {e}")
        print("\n可能原因：")
        print("  1. 设备名称错误")
        print("  2. 麦克风权限问题")
        print("  3. ffmpeg配置问题")
        return False


def generate_config(device_name: str = "麦克风"):
    """生成配置文件"""
    print("\n" + "="*60)
    print("配置文件生成")
    print("="*60)
    
    config = {
        'audio': {
            'sample_rate': 16000,
            'channels': 1,
            'device_name': device_name,
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
            '创建', '新建', '生成', '读取', '打开', '查看',
            '编辑', '修改', '删除', '移除', '运行', '执行',
            '写代码', '搜索', '查找', '测试', '显示', '列出'
        ],
        'logging': {
            'voice_log': 'logs/voice.log',
            'command_log': 'logs/commands.log',
            'level': 'INFO',
            'max_size': 10485760,
            'backup_count': 5
        }
    }
    
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        print(f"\n✓ 配置文件已生成: {config_path}")
        print("\n配置内容:")
        print(f"  - 音频设备: {device_name}")
        print(f"  - Whisper模型: base")
        print(f"  - 语言: zh (中文)")
        print(f"  - 关键词数量: {len(config['keywords'])}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 配置文件生成失败: {e}")
        return False


def interactive_setup():
    """交互式配置设置"""
    print("\n" + "="*60)
    print("语音助手配置助手")
    print("="*60)
    
    print("\n步骤1: 检测音频设备")
    devices = check_audio_devices()
    
    if not devices:
        print("\n无法继续配置，请先连接麦克风")
        return
    
    print("\n步骤2: 选择设备")
    print("\n请输入设备编号（直接回车使用默认'麦克风'）:")
    
    choice = input().strip()
    
    if choice:
        try:
            index = int(choice) - 1
            if 0 <= index < len(devices):
                selected_device = devices[index]
                if "audio=" in selected_device:
                    device_name = selected_device.split("audio=")[1].strip()
                else:
                    device_name = selected_device
            else:
                print("编号无效，使用默认设备")
                device_name = "麦克风"
        except ValueError:
            print("输入无效，使用默认设备")
            device_name = "麦克风"
    else:
        device_name = "麦克风"
    
    print(f"\n已选择设备: {device_name}")
    
    print("\n步骤3: 测试录音")
    print("\n是否测试录音功能？(y/n):")
    
    if input().strip().lower() == 'y':
        test_recording(device_name=device_name)
    
    print("\n步骤4: 生成配置")
    generate_config(device_name=device_name)
    
    print("\n" + "="*60)
    print("配置完成")
    print("="*60)
    print("\n下一步:")
    print("  1. 运行测试: python tests/test_modules.py")
    print("  2. 启动助手: python src/main.py")
    print("="*60)


def main():
    """主函数"""
    interactive_setup()


if __name__ == "__main__":
    main()