# -*- coding: utf-8 -*-
"""
Pytest 配置文件

配置 pytest fixtures 和插件。
"""

import asyncio
import os
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


@pytest.fixture(scope="session")
def test_config_path():
    """测试配置文件路径"""
    return Path(__file__).parent / "uniclaw.test.json"


@pytest.fixture(scope="session")
def kimi_env_vars():
    """Kimi LLM 环境变量配置
    
    优先级:
    1. 环境变量 ANTHROPIC_BASE_URL, ANTHROPIC_API_KEY
    2. tests/uniclaw.test.json 配置文件
    
    使用方式:
       $env:ANTHROPIC_BASE_URL="https://api.moonshot.cn/anthropic"
       $env:ANTHROPIC_API_KEY="sk-kimi-xxx"
       pytest -m llm
    """
    import json
    
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    # 如果环境变量未设置，从测试配置文件读取
    if not base_url or not api_key:
        test_config_path = Path(__file__).parent / "uniclaw.test.json"
        if test_config_path.exists():
            with open(test_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            providers = config.get("model", {}).get("providers", {})
            kimi_config = providers.get("kimi", {})
            
            if not base_url:
                base_url = kimi_config.get("base_url", "")
            if not api_key:
                api_key = kimi_config.get("api_key", "")
    
    if not base_url or not api_key:
        pytest.skip("ANTHROPIC_BASE_URL and ANTHROPIC_API_KEY must be set for LLM tests (or configure in tests/uniclaw.test.json)")
    
    return {"base_url": base_url, "api_key": api_key}


@pytest.fixture
def skill_registry():
    """创建空的 SkillRegistry"""
    from app.uniclaw.skills.registry import SkillRegistry
    return SkillRegistry()


@pytest.fixture
def sample_skill_handler():
    """示例 skill handler，使用 RunContext 类型注解"""
    from typing import TYPE_CHECKING
    
    if TYPE_CHECKING:
        from pydantic_ai import RunContext
        from app.uniclaw.core.deps import SkillDeps
    
    async def handler(ctx: "RunContext[SkillDeps]", query: str) -> dict:
        """示例工具函数"""
        return {"result": f"Processed: {query}"}
    
    return handler


# pytest 配置
def pytest_configure(config):
    """配置 pytest markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests requiring live services (set JIRA_E2E=1 etc.)"
    )
    config.addinivalue_line(
        "markers", "llm: marks tests that require LLM API calls (needs ANTHROPIC_API_KEY)"
    )

