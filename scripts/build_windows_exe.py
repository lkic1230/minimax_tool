"""
Windows 打包脚本：使用 PyInstaller 生成 onedir（exe + dll）分发目录。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def load_app_config(project_root: Path) -> dict:
    defaults = {
        "app_name": "MiniMaxAI",
        "version": "0.0.1",
    }
    config_path = project_root / "app_config.json"
    if not config_path.exists():
        return defaults
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return defaults

    app_name = str(data.get("app_name", defaults["app_name"])).strip() or defaults["app_name"]
    version = str(data.get("version", defaults["version"])).strip() or defaults["version"]
    return {"app_name": app_name, "version": version}


def sanitize_name(text: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    safe = re.sub(r"-{2,}", "-", safe).strip("-")
    return safe or "MiniMaxAI"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MiniMax Qt app to exe+dll (PyInstaller onedir)")
    parser.add_argument("--name", default=None, help="覆盖 app_config.json 中的 app_name")
    parser.add_argument("--version", default=None, help="覆盖 app_config.json 中的 version")
    parser.add_argument(
        "--mode",
        choices=["release", "debug"],
        default="release",
        help="构建模式：release 或 debug（默认: release）",
    )
    parser.add_argument("--clean", action="store_true", help="构建前清理本次目标目录")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    entry_script = project_root / "src" / "qt_main.py"
    app_config = load_app_config(project_root)
    app_name = args.name if args.name else app_config["app_name"]
    app_version = args.version if args.version else app_config["version"]
    artifact_name = f"{sanitize_name(app_name)}-{sanitize_name(app_version)}"

    mode_title = "Release" if args.mode == "release" else "Debug"
    timestamp = datetime.now().strftime("%y%m%d-%H%M%S")
    builds_root = project_root / "builds" / f"{mode_title}-{timestamp}"
    dist_dir = builds_root / "dist"
    work_dir = builds_root / "build"
    spec_dir = builds_root / "spec"

    if not entry_script.exists():
        print(f"[错误] 未找到入口文件: {entry_script}")
        raise SystemExit(1)

    if args.clean and builds_root.exists():
        print(f"[清理] 删除旧构建目录: {builds_root}")
        shutil.rmtree(builds_root, ignore_errors=True)

    for path in (dist_dir, work_dir, spec_dir):
        path.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--noupx",
        "--name",
        artifact_name,
        "--paths",
        str(project_root / "src"),
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        str(entry_script),
    ]
    app_config_path = project_root / "app_config.json"
    if app_config_path.exists():
        cmd.extend(["--add-data", f"{app_config_path};."])
    if args.mode == "release":
        cmd.append("--windowed")
    else:
        cmd.extend(["--console", "--debug", "all"])

    print(f"[开始] 使用 PyInstaller 打包 (onedir, noupx, mode={mode_title})...")
    print(f"[应用] {app_name} v{app_version}")
    print("[命令] " + " ".join(cmd))
    run(cmd, cwd=project_root)

    output_dir = dist_dir / artifact_name
    print("[完成] 构建成功")
    print(f"[构建目录] {builds_root}")
    print(f"[产物] {output_dir}")
    print("        目录内应包含 exe 与若干 dll 文件")


if __name__ == "__main__":
    main()
