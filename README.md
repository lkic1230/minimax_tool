# MiniMax AI 生成工具

支持语音生成、图像生成、视频生成、音乐生成的命令行工具和Web界面。

## 功能特性

- 🎤 **语音生成** - 支持多种语音模型和音色，可调节语速、情感
- 🖼️ **图像生成** - 支持文生图/图生图，多种风格和比例
- 🎬 **视频生成** - 支持文生视频、图生视频，多种分辨率
- 🎵 **音乐生成** - 支持原创音乐和翻唱，灵活控制风格

## 目录结构

```
minimax_tool/
├── src/                        # 核心源代码
│   ├── __init__.py
│   ├── config.py                # 配置管理（加密存储API密钥）
│   ├── client.py                # MiniMax API客户端
│   ├── cli.py                   # 命令行界面入口
│   ├── webui.py                 # Web界面入口
│   ├── api/                     # API路由模块
│   │   ├── __init__.py
│   │   ├── speech.py            # 语音生成API
│   │   ├── image.py             # 图像生成API
│   │   ├── video.py             # 视频生成API
│   │   ├── music.py             # 音乐生成API
│   │   └── config.py            # 配置API
│   └── modules/                # 功能模块（预留扩展）
├── templates/                   # Web界面模板
│   └── index.html
├── static/                      # 静态资源
├── cli.bat                      # CLI启动脚本
├── webui.bat                    # WebUI启动脚本
├── install.bat                   # 安装脚本
├── setup-api.bat                # API配置脚本
├── setup-api.py                 # API配置Python脚本
├── requirements.txt              # 依赖列表
└── README.md
```

## 安装

### Windows 用户（推荐）

1. 先双击运行 `install.bat`（安装依赖、安装工具、绑定当前设备）
2. 再双击运行 `run-qt.bat` 打开桌面工具
3. 首次进入后到「配置」页签设置 API Key

### Linux/macOS 或手动安装

```bash
# 安装依赖（推荐使用清华镜像源）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装工具
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 快速开始

### 推荐流程（Windows）

1. 运行 `install.bat`
2. 运行 `run-qt.bat`
3. 在工具的「配置」页签填写并保存 API Key
4. 返回各功能页签开始使用

| 文件 | 说明 |
|------|------|
| `install.bat` | 一键安装依赖、安装工具并绑定设备 |
| `run-qt.bat` | 启动桌面版 Qt 工具 |
| `webui.bat` | 启动 WebUI 界面 |
| `cli.bat` | CLI 命令行工具 |

### WebUI 使用

1. 双击 `webui.bat` 启动
2. 访问 `http://127.0.0.1:5000`
3. 在界面配置 API 密钥
4. 使用各个生成功能

### 调试面板

- 点击右下角 **🛠️** 按钮打开实时日志面板
- 可查看请求/响应日志、错误信息
- 支持日志下载和清空

### CLI 使用

```bash
# 查看帮助
python -m minimax_tool.src.cli --help

# 配置管理
python -m minimax_tool.src.cli config show           # 显示当前配置
python -m minimax_tool.src.cli config set-key <KEY>  # 设置API密钥

# 语音生成
python -m minimax_tool.src.cli speech generate -t "你好世界"

# 图像生成
python -m minimax_tool.src.cli image generate -p "一只可爱的猫咪"

# 视频生成
python -m minimax_tool.src.cli video generate -p "太阳从海面升起"

# 音乐生成
python -m minimax_tool.src.cli music generate -p "欢快的电子音乐"

# 列出所有可用模型
python -m minimax_tool.src.cli models

# 列出所有音色
python -m minimax_tool.src.cli voices
```

## 配置 API 密钥（必须）

### 方式一：WebUI 配置
在 Web 界面中直接输入 API 密钥并保存。

### 方式二：CLI 配置
```bash
python -m minimax_tool.src.cli config set-key your_api_key_here
```

### 方式三：Qt 工具配置（推荐）
启动 `run-qt.bat` 后，在「配置」页签输入并保存 API Key。

## 配置文件

API 密钥以加密形式存储在用户目录下：
- Windows: `%APPDATA%\minimax_tool\config.enc`
- Linux/Mac: `~/.minimax_tool/config.enc`

## 支持的模型

### 语音模型
- `speech-2.8-hd` - 高清语音，情绪渲染自然
- `speech-2.8-turbo` - 快速语音，极致速度
- `speech-2.6-hd` / `speech-2.6-turbo` - 稳定语音

### 图像模型
- `image-01` - 写实风格
- `image-01-live` - 插画/卡通风格

### 视频模型
- `MiniMax-Hailuo-2.3` - 最新模型，动作表情突破
- `MiniMax-Hailuo-02` - 1080p高清
- `MiniMax-Hailuo-2.3-Fast` - 快速图生视频

### 音乐模型
- `music-2.6` - 原创音乐
- `music-cover` - 翻唱

## 版权声明

本工具仅用于学习和研究使用，请遵守 MiniMax 平台的使用条款。
