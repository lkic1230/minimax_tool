"""
MiniMax AI Generation Tool 安装配置
"""
from setuptools import find_packages, setup


module_packages = find_packages(where='src/modules')
all_packages = [
    'minimax_tool',
    'minimax_tool.src',
    'minimax_tool.src.modules',
]
all_packages.extend(
    f'minimax_tool.src.modules.{pkg}' for pkg in module_packages if pkg
)

setup(
    name='minimax-tool',
    version='1.0.0',
    description='MiniMax AI 生成工具 - 支持语音/图像/视频/音乐生成',
    author='MiniMax Tool Team',
    packages=sorted(set(all_packages)),
    package_dir={
        'minimax_tool': '.',
        'minimax_tool.src': 'src',
        'minimax_tool.src.modules': 'src/modules',
    },
    include_package_data=True,
    install_requires=[
        'flask>=2.3.0',
        'requests>=2.31.0',
        'click>=8.1.0',
        'tabulate>=0.9.0',
        'cryptography>=41.0.0',
        'werkzeug>=2.3.0',
        'PySide6>=6.5.0',
    ],
    package_data={
        'minimax_tool': ['templates/*', 'static/*'],
    },
    entry_points={
        'console_scripts': [
            'minimax=minimax_tool.src.cli:run_cli',
        ],
    },
    python_requires='>=3.8',
)
