# Voice Assistant

Python语音助手 - 解放双手，语音控制opencode干活

> **核心目标：用语音控制opencode，彻底解放双手**
>
> **实现路径：语音输入 → 自动转文字 → opencode CLI执行 → 开发任务完成**

## 功能

- 🎤 实时语音识别（本地Whisper模型，无需云端API）
- 🗣️ 语音命令检测（关键词白名单过滤）
- 🤖 自动调用opencode执行任务（直接执行模式）
- 📝 完整日志记录（voice.log + commands.log）
- 🔒 安全措施（关键词白名单、危险命令检测、超时控制）

## 架构设计

**三层架构：适配器层隔离所有外部依赖**

```
┌─────────────────────────────────────────────────────────────┐
│                      业务逻辑层                               │
│  (audio_capture, speech_recognizer, keyword_detector,       │
│   opencode_executor, main)                                  │
│  - 不依赖任何外部实现                                         │
│  - 只依赖适配器接口                                           │
│  - 纯业务逻辑，易于测试                                       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                      适配器层                                │
│  (adapters/)                                                │
│  - ISubprocessAdapter → subprocess.run()                    │
│  - IWhisperAdapter → whisper.load_model()                   │
│  - IFFmpegAdapter → ffmpeg工具                               │
│  - IOpenCodeAdapter → opencode CLI                          │
│  - IYAMLAdapter → yaml.safe_load()                          │
│  - IOSAdapter → os.remove()                                 │
│  - ILoggingAdapter → logging.basicConfig()                  │
│  - ISignalAdapter → signal.signal()                         │
│                                                              │
│  ✅ 提供统一接口                                             │
│  ✅ 封装外部实现                                             │
│  ✅ 方便mock/stub测试                                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    外部依赖层                                 │
│  - subprocess (Python标准库)                                │
│  - whisper (openai-whisper)                                 │
│  - ffmpeg (外部工具)                                         │
│  - opencode (外部CLI)                                        │
│  - yaml (PyYAML)                                            │
│  - os, logging, signal (Python标准库)                       │
└─────────────────────────────────────────────────────────────┘
```

**架构优势：**

| 优势 | 说明 |
|------|------|
| **易于测试** | 业务逻辑不依赖外部实现，可注入mock/stub |
| **易于维护** | 外部实现变更只需修改适配器，不影响业务逻辑 |
| **易于扩展** | 新增功能只需添加适配器接口和实现 |
| **易于Mock** | 测试时可用MockAdapter替换真实适配器 |

**测试示例（不生成测试代码，仅展示设计）：**

```python
# 测试audio_capture时，注入MockFFmpegAdapter
mock_ffmpeg = MockFFmpegAdapter()
audio = AudioCapture(ffmpeg_adapter=mock_ffmpeg)

# mock返回预设结果，无需真实ffmpeg
assert audio.record_segment(5) == "/tmp/test.wav"
```

## 技术栈

| 技术层 | 选型 | 版本 | 说明 |
|--------|------|------|------|
| **音频采集** | ffmpeg subprocess | 8.1.1 | 跨平台、无AppX限制 |
| **语音识别** | OpenAI Whisper | base (145MB) | 本地处理、支持中文 |
| **推理引擎** | PyTorch | 2.11.0+cpu | 无需GPU、性能可接受 |
| **CLI调用** | subprocess.run() | Python标准库 | 简单可靠 |
| **命令执行** | opencode CLI | 1.14.41 | 直接执行模式 |

## 快速开始

### 1. 安装依赖

```bash
cd voice-assistant
pip install -r requirements.txt
```

**依赖项清单：**
- Python 3.12.10 ✅
- openai-whisper 20250625 ✅
- torch 2.11.0+cpu ✅
- numpy 2.4.4 ✅
- ffmpeg 8.1.1 ✅
- opencode CLI 1.14.41 ✅

### 2. 启动语音助手

```bash
python src/main.py
```

## 使用说明

### 语音命令格式

**格式：** `[关键词] + [参数]`

### 支持的关键词

| 类别 | 关键词列表 | 示例命令 |
|------|-----------|---------|
| **创建类** | 创建、新建、生成、建立 | "创建文件 main.py" |
| **读取类** | 读取、打开、查看、浏览 | "读取文件 app.py" |
| **编辑类** | 编辑、修改、更新、调整 | "编辑文件 test.py" |
| **删除类** | 删除、移除、清除、去掉 | "删除文件 old.py" |
| **执行类** | 运行、执行、启动、调用 | "运行测试" |
| **生成类** | 写代码、生成代码、编写、编码 | "写代码定义函数" |
| **搜索类** | 搜索、查找、寻找、定位 | "搜索文件 test" |
| **显示类** | 显示、列出、展示、输出 | "显示目录" |
| **测试类** | 测试、调试、验证、检查 | "测试模块" |

### 使用示例

对着麦克风说出命令：
- "创建文件 main.py" → 自动创建文件
- "读取文件 app.py" → 自动读取文件
- "运行测试" → 自动运行测试
- "写代码实现功能" → AI自动生成代码

### 运行示例脚本

```bash
python examples/usage_examples.py
```

## 配置说明

编辑 `config/config.yaml` 文件：

### 音频配置
```yaml
audio:
  sample_rate: 16000      # Whisper要求的采样率
  channels: 1             # 单声道
  device_name: "麦克风"    # 音频设备名称
  segment_duration: 5     # 录音时长（秒）
```

### Whisper配置
```yaml
whisper:
  model_size: "base"      # 模型大小（tiny/base/small/medium/large）
  language: "zh"          # 语言（zh=中文，en=英文）
  temperature: 0.0        # 采样温度（0=确定性输出）
```

### 关键词配置
```yaml
keywords:
  创建类: ["创建", "新建", "生成"]
  读取类: ["读取", "打开", "查看"]
  # ...更多关键词类别
```

## 安全措施

| 安全层 | 实现 |
|--------|------|
| **关键词白名单** | 只识别预设关键词，防止任意命令执行 |
| **危险命令检测** | 检测shell注入符号（;&|$等） |
| **执行日志** | 记录所有操作到logs/commands.log |
| **错误处理** | 捕获subprocess异常，防止崩溃 |
| **超时控制** | 60秒超时限制 |

## 性能指标

- **录音延迟：** 5秒/段
- **识别延迟：** 2-5秒
- **总延迟：** 7-10秒
- **内存占用：** ~500 MB（Whisper base模型）
- **CPU占用：** 30-50%（识别时）

## 项目结构

```
voice-assistant/
├── src/                    # 源代码
│   ├── audio_capture.py    # 音频采集模块
│   ├── speech_recognizer.py # 语音识别模块
│   ├── keyword_detector.py # 关键词检测模块
│   └── main.py             # 主程序入口
├── config/                 # 配置文件
│   └ config.yaml           # 主配置文件
├── design/                 # 设计文档
│   └ rfc-001.md            # RFC技术方案
├── logs/                   # 日志目录
│   ├── voice.log           # 语音日志
│   └ commands.log          # 命令日志
│   └ audio_archive/        # 录音归档目录
├── requirements.txt        # Python依赖
└── README.md               # 项目说明
```

## 参考资料

- [RFC-001技术方案](design/rfc-001.md) - 完整设计文档
- [OpenAI Whisper](https://github.com/openai/whisper) - 语音识别
- [FFmpeg](https://ffmpeg.org/) - 音频采集
- [opencode](https://github.com/sst/opencode) - CLI工具

## 注意事项

⚠️ **直接执行模式：** 识别到关键词后立即执行，无需用户确认

⚠️ **关键词白名单：** 只识别预设关键词，保障安全性

⚠️ **音频设备：** 需正确配置麦克风设备名称

⚠️ **模型下载：** Whisper base模型首次运行需下载（约145MB）

## License

MIT