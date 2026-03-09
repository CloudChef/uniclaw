# -*- coding: utf-8 -*-
"""
Pytest 配置文件

配置 pytest fixtures 和插件。
"""

import asyncio
import sys
from pathlib import Path

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环 fixture"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def anyio_backend():
    """指定 anyio 后端"""
    return "asyncio"


# pytest 配置
def pytest_configure(config):
    """配置 pytest markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
