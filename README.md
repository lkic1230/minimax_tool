# MiniMax AI 生成工具

当前项目提供 Qt 桌面工具与 CLI，支持文本对话、图像、视频、音乐、语音等能力。

## 功能特性

- 🎤 **语音生成**：多模型、多音色，可调节速度和情感参数
- 🖼️ **图像生成**：支持文生图/图生图与常见比例参数
- 🎬 **视频生成**：支持文生视频/图生视频
- 🎵 **音乐生成**：支持原创与翻唱
- 💬 **文本对话**：多轮对话、历史记录、Markdown 显示

## 当前目录结构（精简）

```text
minimax_tool/
├─ src/
│  ├─ qt_main.py
│  ├─ qt_main_window.py
│  ├─ cli.py
│  └─ modules/
│     ├─ api/
│     ├─ core/
│     └─ ui/
├─ scripts/
│  └─ build_windows_exe.py
├─ tests/
├─ app_config.json
├─ install.bat
├─ run-qt.bat
├─ build-release.bat
├─ build-debug.bat
├─ requirements.txt
└─ README.md
```

## 安装

### Windows（推荐）

1. 双击运行 `install.bat`（安装依赖、PyInstaller、项目本体）
2. 双击运行 `run-qt.bat` 启动桌面工具
3. 在「配置」页签填写 API Key

### 手动安装

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 打包（Windows）

- 发布版：运行 `build-release.bat`
- 调试版：运行 `build-debug.bat`
- 名称与版本：编辑根目录 `app_config.json`
- 产物目录：
- `builds/Release-<yymmdd-hhmmss>/dist/<名称>-<版本号>/`
- `builds/Debug-<yymmdd-hhmmss>/dist/<名称>-<版本号>/`

## API Key 配置

- Qt（推荐）：启动 `run-qt.bat` 后，在「配置」页签设置
- CLI：

```bash
python -m minimax_tool.src.cli config set-key your_api_key_here
```

## CLI 示例

```bash
python -m minimax_tool.src.cli --help
python -m minimax_tool.src.cli config show
python -m minimax_tool.src.cli models
python -m minimax_tool.src.cli voices
```

## 测试

- 测试说明、用例时间记录见：`tests/README.md`
- 运行命令：

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

## 配置文件位置

- API Key 加密存储：
- Windows：`%APPDATA%\minimax_tool\config.enc`
- Linux/macOS：`~/.minimax_tool/config.enc`

## 版权声明

本工具仅用于学习和研究，请遵守 MiniMax 平台的使用条款。
