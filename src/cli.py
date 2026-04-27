"""
MiniMax CLI - 命令行界面
"""
import os
import sys
import json
import time
import click
from pathlib import Path
from tabulate import tabulate

from .modules.core import get_config_manager
from .modules.api import MiniMaxClient


def get_client() -> MiniMaxClient:
    """获取已配置的API客户端"""
    config = get_config_manager()
    api_key = config.get_api_key()

    if not api_key:
        click.echo(click.style("错误: 请先配置API密钥", fg='red', bold=True))
        # 动态获取包名，避免硬编码
        package_name = __name__.split('.')[0] if '.' in __name__ else 'minimax_tool'
        click.echo(f"运行 'python -m {package_name}.src.cli config set-key YOUR_API_KEY' 来设置")
        sys.exit(1)

    return MiniMaxClient(api_key, config.get_output_dir())


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """MiniMax AI 生成工具 - 支持语音/图像/视频/音乐生成"""
    pass


# ==================== 配置命令 ====================

@cli.group()
def config():
    """配置管理"""
    pass


@config.command('show')
def config_show():
    """显示当前配置"""
    cfg = get_config_manager()
    info = cfg.get_config_info()

    table = [
        ["配置目录", info['config_dir']],
        ["输出目录", info['output_dir']],
        ["API密钥", info['api_key_preview'] if info['api_key_preview'] else "未设置"]
    ]

    click.echo("\n" + tabulate(table, tablefmt='plain') + "\n")


@config.command('set-key')
@click.argument('api_key')
def config_set_key(api_key):
    """设置API密钥"""
    cfg = get_config_manager()
    if cfg.set_api_key(api_key):
        click.echo(click.style("✓ API密钥已保存", fg='green'))
    else:
        click.echo(click.style("✗ 保存失败", fg='red'))


@config.command('set-output')
@click.argument('output_dir')
def config_set_output(output_dir):
    """设置默认输出目录"""
    cfg = get_config_manager()
    path = Path(output_dir)

    if not path.exists():
        if click.confirm(f"目录不存在，是否创建?"):
            path.mkdir(parents=True, exist_ok=True)
        else:
            return

    if cfg.set_output_dir(str(path)):
        click.echo(click.style(f"✓ 输出目录已设置为: {path}", fg='green'))
    else:
        click.echo(click.style("✗ 保存失败", fg='red'))


@config.command('delete-key')
def config_delete_key():
    """删除已保存的API密钥"""
    if click.confirm("确定要删除API密钥吗?"):
        cfg = get_config_manager()
        if cfg.delete_api_key():
            click.echo(click.style("✓ API密钥已删除", fg='green'))
        else:
            click.echo(click.style("✗ 删除失败", fg='red'))


@config.command('bind-device')
@click.option('--force', is_flag=True, help='强制重绑当前设备（会影响已有加密配置可读性）')
def config_bind_device(force):
    """绑定当前设备的 MAC 信息"""
    cfg = get_config_manager()
    if cfg.bind_device(force=force):
        click.echo(click.style("✓ 设备绑定成功", fg='green'))
    else:
        click.echo(click.style("✗ 设备绑定失败（当前设备与已绑定设备不一致）", fg='red'))


# ==================== 模型命令 ====================

@cli.command('models')
def list_models():
    """列出所有可用模型"""
    client = get_client()
    models = client.get_available_models()

    click.echo("\n" + click.style("MiniMax 可用模型", fg='cyan', bold=True) + "\n")

    for category, model_list in models.items():
        click.echo(click.style(f"\n◆ {category}", fg='yellow', bold=True))
        for model in model_list:
            click.echo(f"  {model}")


@cli.command('voices')
def list_voices():
    """列出所有可用音色"""
    client = get_client()
    voices = client.list_voices()

    table = [["ID", "名称", "性别"]]
    for voice in voices:
        table.append([voice['id'], voice['name'], voice['gender']])

    click.echo("\n" + tabulate(table, headers='firstrow', tablefmt='grid') + "\n")


# ==================== 语音命令 ====================

@cli.group()
def speech():
    """语音生成"""
    pass


@speech.command('generate')
@click.option('--text', '-t', required=True, help='要转换的文本')
@click.option('--model', '-m', default='speech-2.8-hd', help='语音模型')
@click.option('--voice', '-v', default='female-tianmei', help='音色ID')
@click.option('--speed', '-s', default=1.0, help='语速 (0.5-2.0)')
@click.option('--emotion', '-e', default='neutral', help='情感 (neutral/happy/sad/angry)')
@click.option('--output', '-o', help='输出文件路径')
def speech_generate(text, model, voice, speed, emotion, output):
    """生成语音"""
    client = get_client()

    click.echo(f"正在生成语音 (模型: {model}, 音色: {voice})...")

    try:
        result = client.generate_speech(
            text=text,
            model=model,
            voice_id=voice,
            speed=speed,
            emotion=emotion,
            output_format='hex' if output else 'url',
            save_path=output
        )

        if result.get('saved_path'):
            click.echo(click.style(f"\n✓ 语音已保存到: {result['saved_path']}", fg='green'))

            if result.get('extra_info'):
                info = result['extra_info']
                click.echo(f"\n音频信息:")
                click.echo(f"  时长: {info.get('audio_length', 0) / 1000:.1f}秒")
                click.echo(f"  采样率: {info.get('audio_sample_rate', 0)}Hz")
        else:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        click.echo(click.style(f"\n✗ 生成失败: {e}", fg='red'))
        sys.exit(1)


# ==================== 图像命令 ====================

@cli.group()
def image():
    """图像生成"""
    pass


@image.command('generate')
@click.option('--prompt', '-p', required=True, help='图像描述')
@click.option('--model', '-m', default='image-01', help='图像模型')
@click.option('--count', '-n', default=1, help='生成数量 (1-9)')
@click.option('--ratio', '-r', default='1:1', help='宽高比 (1:1/16:9/4:3等)')
@click.option('--width', '-w', default=1024, help='宽度')
@click.option('--height', '-h', default=1024, help='高度')
@click.option('--style', '-s', help='画风 (仅image-01-live)')
@click.option('--output', '-o', help='输出文件路径')
def image_generate(prompt, model, count, ratio, width, height, style, output):
    """生成图像"""
    client = get_client()

    click.echo(f"正在生成图像 (模型: {model}, 数量: {count})...")

    try:
        result = client.generate_image(
            prompt=prompt,
            model=model,
            n=count,
            aspect_ratio=ratio,
            width=width,
            height=height,
            style=style,
            save_path=output
        )

        saved_paths = result.get('saved_paths', [])
        if saved_paths:
            click.echo(click.style(f"\n✓ 已生成 {len(saved_paths)} 张图像:", fg='green'))
            for path in saved_paths:
                click.echo(f"  - {path}")
        else:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        click.echo(click.style(f"\n✗ 生成失败: {e}", fg='red'))
        sys.exit(1)


# ==================== 视频命令 ====================

@cli.group()
def video():
    """视频生成"""
    pass


@video.command('generate')
@click.option('--prompt', '-p', required=True, help='视频描述')
@click.option('--model', '-m', default='MiniMax-Hailuo-2.3', help='视频模型')
@click.option('--duration', '-d', default=6, type=int, help='时长 (6/10秒)')
@click.option('--resolution', '-r', default='768P', help='分辨率 (512P/720P/768P/1080P)')
@click.option('--output', '-o', help='输出文件路径')
def video_generate(prompt, model, duration, resolution, output):
    """文生视频"""
    client = get_client()

    click.echo(f"正在生成视频 (模型: {model}, 时长: {duration}秒)...")

    try:
        result = client.generate_video(
            prompt=prompt,
            model=model,
            duration=duration,
            resolution=resolution,
            save_path=output
        )

        task_id = result.get('task_id')
        if task_id:
            click.echo(click.style(f"\n✓ 任务已提交", fg='green'))
            click.echo(f"任务ID: {task_id}")
            click.echo(f"\n运行 'python -m minimax_tool.src.cli video query --task-id {task_id}' 查询状态")
            click.echo(f"运行 'python -m minimax_tool.src.cli video download --task-id {task_id}' 下载视频")
        else:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        click.echo(click.style(f"\n✗ 生成失败: {e}", fg='red'))
        sys.exit(1)


@video.command('generate-from-image')
@click.option('--image', '-i', required=True, help='起始帧图片路径或URL')
@click.option('--prompt', '-p', default='', help='视频描述')
@click.option('--model', '-m', default='MiniMax-Hailuo-2.3', help='视频模型')
@click.option('--duration', '-d', default=6, type=int, help='时长')
@click.option('--resolution', '-r', default='768P', help='分辨率')
@click.option('--output', '-o', help='输出文件路径')
def video_generate_from_image(image, prompt, model, duration, resolution, output):
    """图生视频"""
    client = get_client()

    click.echo(f"正在生成视频 (模型: {model}, 时长: {duration}秒)...")

    try:
        result = client.generate_video_from_image(
            image=image,
            prompt=prompt,
            model=model,
            duration=duration,
            resolution=resolution,
            save_path=output
        )

        task_id = result.get('task_id')
        if task_id:
            click.echo(click.style(f"\n✓ 任务已提交", fg='green'))
            click.echo(f"任务ID: {task_id}")
            click.echo(f"\n运行 'python -m minimax_tool.src.cli video query --task-id {task_id}' 查询状态")
            click.echo(f"运行 'python -m minimax_tool.src.cli video download --task-id {task_id}' 下载视频")
        else:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        click.echo(click.style(f"\n✗ 生成失败: {e}", fg='red'))
        sys.exit(1)


@video.command('query')
@click.option('--task-id', '-t', required=True, help='任务ID')
def video_query(task_id):
    """查询视频任务状态"""
    client = get_client()

    try:
        result = client.query_video_task(task_id)
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        click.echo(click.style(f"\n✗ 查询失败: {e}", fg='red'))
        sys.exit(1)


@video.command('download')
@click.option('--task-id', '-t', required=True, help='任务ID')
@click.option('--output', '-o', help='输出文件路径')
def video_download(task_id, output):
    """下载生成的视频"""
    client = get_client()

    click.echo(f"正在下载视频...")

    try:
        result = client.download_video(task_id, output)

        saved_path = result.get('saved_path')
        if saved_path:
            click.echo(click.style(f"\n✓ 视频已保存到: {saved_path}", fg='green'))
        else:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        click.echo(click.style(f"\n✗ 下载失败: {e}", fg='red'))
        sys.exit(1)


# ==================== 文本对话命令 ====================

@cli.group()
def chat():
    """文本对话"""
    pass


@chat.command('send')
@click.option('--message', '-m', required=True, help='要发送的消息')
@click.option('--model', default='MiniMax-M2.7', help='对话模型')
@click.option('--system', '-s', default='', help='System 提示词')
@click.option('--max-tokens', type=int, default=512, help='最大回复 Token')
@click.option('--temperature', '-t', type=float, default=0.7, help='温度')
@click.option('--top-p', type=float, default=0.95, help='Top P')
def chat_send(message, model, system, max_tokens, temperature, top_p):
    """发送单条对话消息"""
    client = get_client()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    click.echo(f"正在发送消息 (模型: {model})...")

    try:
        result = client.chat_completions(
            messages=messages,
            model=model,
            stream=False,
            max_completion_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )

        choices = result.get("choices", [])
        if choices:
            reply = choices[0].get("message", {}).get("content", "")
            click.echo(f"\n{reply}")

            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens")
            if total_tokens is not None:
                click.echo(click.style(f"\n（总 Token: {total_tokens}）", fg="cyan"))
        else:
            click.echo(click.style("✗ 未获取到有效回复", fg='red'))
            sys.exit(1)

    except Exception as e:
        click.echo(click.style(f"\n✗ 对话失败: {e}", fg='red'))
        sys.exit(1)


@chat.command('interactive')
@click.option('--model', default='MiniMax-M2.7', help='对话模型')
@click.option('--system', '-s', default='', help='System 提示词')
@click.option('--max-tokens', type=int, default=512, help='最大回复 Token')
@click.option('--temperature', '-t', type=float, default=0.7, help='温度')
@click.option('--top-p', type=float, default=0.95, help='Top P')
def chat_interactive(model, system, max_tokens, temperature, top_p):
    """进入交互式多轮对话"""
    client = get_client()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    click.echo(click.style("交互式对话模式（输入 /quit 退出）\n", fg='cyan', bold=True))

    while True:
        try:
            user_input = click.prompt(click.style("你", fg='green'), default='', show_default=False)
        except (KeyboardInterrupt, EOFError):
            click.echo("\n再见！")
            break

        if not user_input.strip():
            continue
        if user_input.strip() == '/quit':
            click.echo("再见！")
            break

        messages.append({"role": "user", "content": user_input.strip()})

        try:
            result = client.chat_completions(
                messages=messages,
                model=model,
                stream=False,
                max_completion_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

            choices = result.get("choices", [])
            if choices:
                reply = choices[0].get("message", {}).get("content", "")
                click.echo(click.style(f"助手: ", fg='yellow'), nl=False)
                click.echo(reply)
                messages.append({"role": "assistant", "content": reply})

                usage = result.get("usage", {})
                total_tokens = usage.get("total_tokens")
                if total_tokens is not None:
                    click.echo(click.style(f"（累计 {len(messages)//2} 轮，本次 Token: {total_tokens}）", fg="cyan"))
            else:
                click.echo(click.style("助手: ✗ 未获取到有效回复", fg='red'))

        except Exception as e:
            click.echo(click.style(f"✗ 对话失败: {e}", fg='red'))
            messages.pop()  # 移除失败的消息


# ==================== 音乐命令 ====================

@cli.group()
def music():
    """音乐生成"""
    pass


@music.command('generate')
@click.option('--prompt', '-p', required=True, help='音乐描述（风格、情绪、场景）')
@click.option('--model', '-m', default='music-2.6', help='音乐模型')
@click.option('--lyrics', '-l', help='歌词（使用\\n分隔）')
@click.option('--instrumental', is_flag=True, help='纯音乐模式')
@click.option('--audio', '-a', help='参考音频URL或路径（用于music-cover）')
@click.option('--output', '-o', help='输出文件路径')
def music_generate(prompt, model, lyrics, instrumental, audio, output):
    """生成音乐"""
    client = get_client()

    click.echo(f"正在生成音乐 (模型: {model})...")

    try:
        # 处理参考音频
        audio_url = None
        audio_base64 = None

        if audio:
            if audio.startswith('http'):
                audio_url = audio
            elif os.path.isfile(audio):
                import base64
                with open(audio, 'rb') as f:
                    audio_base64 = base64.b64encode(f.read()).decode()
            else:
                click.echo(click.style("✗ 参考音频必须是有效的URL或本地文件路径", fg='red'))
                sys.exit(1)

        result = client.generate_music(
            prompt=prompt,
            model=model,
            lyrics=lyrics,
            is_instrumental=instrumental,
            audio_url=audio_url,
            audio_base64=audio_base64,
            output_format='hex' if output else 'url',
            save_path=output
        )

        if result.get('saved_path'):
            click.echo(click.style(f"\n✓ 音乐已保存到: {result['saved_path']}", fg='green'))

            if result.get('extra_info'):
                info = result['extra_info']
                click.echo(f"\n音乐信息:")
                click.echo(f"  时长: {info.get('music_duration', 0) / 1000:.1f}秒")
        else:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        click.echo(click.style(f"\n✗ 生成失败: {e}", fg='red'))
        sys.exit(1)


# 运行CLI
def run_cli():
    """运行CLI"""
    cli()


if __name__ == '__main__':
    run_cli()
