# -*- coding: utf-8 -*-
"""
窗口管理器安装配置
用于支持 setuptools 安装和打包发布
"""

from setuptools import setup, find_packages
from pathlib import Path

VERSION = "2.0.0"


def read_requirements():
    """从 requirements.txt 读取依赖"""
    req_file = Path(__file__).parent / "requirements.txt"
    if req_file.exists():
        with open(req_file, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []


def read_long_description():
    """从 README.md 读取项目详细说明"""
    readme_file = Path(__file__).parent / "README.md"
    if readme_file.exists():
        with open(readme_file, encoding="utf-8") as f:
            return f.read()
    return ""


setup(
    name="windowmanager",
    version=VERSION,
    description="Windows 窗口管理器 - 支持窗口隐藏、热键管理、时间校准",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    author="Stephen Zhao",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/windowmanager",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pyinstaller>=6.0.0",
            "pytest>=7.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    package_data={
        "": ["*.json", "*.png"],
    },
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Desktop Environment",
    ],
    entry_points={
        "console_scripts": [
            "winhide=app:main",
        ],
    },
)
