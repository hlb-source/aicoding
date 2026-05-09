# Voice Assistant

Python语音助手 - 解放双手，语音控制opencode干活

## 功能

- 🎤 实时语音识别（本地Whisper模型）
- 🗣️ 语音命令检测
- 🤖 自动调用opencode执行任务
- 📝 完整日志记录

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行程序

```bash
python src/main.py
```

## 配置

编辑 `config/config.yaml` 文件：

- 音频设备
- Whisper模型大小
- 关键词列表
- opencode路径

## 使用说明

对着麦克风说出命令，例如：
- "创建文件 main.py"
- "读取文件 app.py"
- "运行测试"

## 技术栈

- Python 3.12+
- OpenAI Whisper（本地语音识别）
- FFmpeg（音频采集）
- opencode CLI（命令执行）