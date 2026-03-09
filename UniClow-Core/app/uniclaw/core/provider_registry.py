"""


ServiceProviderRegistry Enterprise service provider registry

management Service-Provider template, instanceconfiguration, Provider Skills register.

Provider:
 providers/
 └── jira/
 ├── PROVIDER.md or jira.md # Provider + parameter Schema
 └── skills/
 ├── create_issue.py # SKILL_METADATA + handler
 └── shared.py # optional code(register Skill)

search(, Skills):
1. {workspace}/providers/(workspace, highest priority)
2. ~/.uniclaw/providers/(user)
3. providers(from uniclaw)

configuration(, instances in):
 {
 "service_providers":{
 "jira":{
 "prod":{"base_url":"...", "username":"...", "token":"${JIRA_TOKEN}"},
 "dev":{"base_url":"...", "username":"...", "token":"${JIRA_DEV_TOKEN}"}
 }
 }
 }
"""

from __future__ import annotations

import functools
import importlib.util
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.uniclaw.skills.registry import SkillRegistry, SkillMetadata

logger = logging.getLogger(__name__)

# models.providers in environment variableparsemode
_ENV_PATTERN = re.compile(r'\$\{(\w+)(?::([^}]*))?\}')

# parameter(list_provider_instances return)
_SENSITIVE_KEYS = frozenset({
    "token", "password", "secret", "api_key", "apikey",
    "access_token", "private_key", "credential",
})


def _resolve_env(value: str) -> str:
    """parse ${VAR_NAME} or ${VAR_NAME:default} for matenvironment variable"""
    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)
        return os.environ.get(var_name, default if default is not None else "")
    return _ENV_PATTERN.sub(_replacer, value)


def _resolve_env_recursive(obj: Any) -> Any:
    """parse dict/list in environment variable"""
    if isinstance(obj, str):
        return _resolve_env(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_recursive(item) for item in obj]
    return obj


def _is_sensitive(key: str) -> bool:
    """parameter"""
    return key.lower() in _SENSITIVE_KEYS


def _redact_config(config: dict[str, Any]) -> dict[str, Any]:
    """configurationparameter,"""
    return {
        k: "***" if _is_sensitive(k) else v
        for k, v in config.items()
    }


class ProviderTemplate:
    """

Provider template

    Attributes:
        name:Provider typename(sub)
        path:Provider directory path
        md_path:PROVIDER.md or MD file path
        skills_dir:skills/ subdirectory path
    
"""

    def __init__(self, name: str, path: Path, md_path: Path, skills_dir: Path):
        self.name = name
        self.path = path
        self.md_path = md_path
        self.skills_dir = skills_dir

    def __repr__(self) -> str:
        return f"ProviderTemplate(name={self.name!r}, path={self.path})"


class ServiceProviderRegistry:
    """


Enterprise service provider registry

 management Provider template, instanceconfiguration, Provider Skills register.

 Example usage:
 ```python
 registry = ServiceProviderRegistry()

 # 1. Provider template
 registry.load_from_directory(Path("~/.uniclaw/providers"))

 # 2. instanceconfiguration
 registry.load_instances_from_config({
 "jira":{
 "prod":{"base_url":"https://jira.corp.com", "token":"secret"},
 }
 })

 # 3. register Provider Skills to SkillRegistry
 registry.register_skills_to(skill_registry)

 # 4.
 providers = registry.list_providers() # ["jira"]
 instances = registry.list_instances("jira") # ["prod"]
 config = registry.get_instance_config("jira", "prod")
 ```
 
"""

    def __init__(self) -> None:
        # Provider type -> ProviderTemplate
        self._templates: dict[str, ProviderTemplate] = {}
        # Provider type -> {instance -> parseparameter dict}
        self._instances: dict[str, dict[str, dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # 
    # ------------------------------------------------------------------

    def load_from_directory(self, providers_dir: Path) -> int:
        """

providers, Provider template

        item:sub contains PROVIDER.md or.md.

        Args:
            providers_dir:providers directory path

        Returns:
            Provider count
        
"""
        providers_dir = Path(providers_dir).expanduser()
        if not providers_dir.is_dir():
            logger.debug("providers 目录不存在: %s", providers_dir)
            return 0

        count = 0
        for sub in sorted(providers_dir.iterdir()):
            if not sub.is_dir() or sub.name.startswith(("_", ".")):
                continue

            # PROVIDER.md or MD
            md_path = self._find_provider_md(sub)
            if md_path is None:
                logger.warning("跳过 Provider 目录 %s: 缺少 PROVIDER.md 或 %s.md", sub.name, sub.name)
                continue

            # skills/ sub(optional,)
            skills_dir = sub / "skills"

            template = ProviderTemplate(
                name=sub.name,
                path=sub,
                md_path=md_path,
                skills_dir=skills_dir,
            )
            self._templates[sub.name] = template
            count += 1
            logger.info("发现 Provider: %s (%s)", sub.name, md_path.name)

        return count

    # ------------------------------------------------------------------
    # instanceconfiguration
    # ------------------------------------------------------------------

    def load_instances_from_config(self, config: dict[str, dict[str, Any]]) -> None:
        """


fromconfiguration instance(contains ${ENV} parse)

 configuration:{provider_type:{instance_name:{param:value}}}

 Args:
 config:service_providers configurationdictionary
 
"""
        for provider_type, instances in config.items():
            if not isinstance(instances, dict):
                logger.warning("Provider %s 配置格式错误，期望 dict，跳过", provider_type)
                continue

            resolved_instances: dict[str, dict[str, Any]] = {}
            for instance_name, params in instances.items():
                if not isinstance(params, dict):
                    logger.warning(
                        "Provider %s.%s 配置格式错误，期望 dict，跳过",
                        provider_type, instance_name,
                    )
                    continue
                resolved_instances[instance_name] = _resolve_env_recursive(params)

            self._instances[provider_type] = resolved_instances
            logger.info(
                "加载 Provider 实例配置: %s -> %s",
                provider_type, list(resolved_instances.keys()),
            )

    # ------------------------------------------------------------------
    # 
    # ------------------------------------------------------------------

    def list_providers(self) -> list[str]:
        """return Provider typelist"""
        # templateandinstanceintype
        all_types = set(self._templates.keys()) | set(self._instances.keys())
        return sorted(all_types)

    def list_instances(self, provider_type: str) -> list[str]:
        """


return Provider instancenamelist

 Args:
 provider_type:Provider type

 Returns:
 instancenamelist, Provider return list
 
"""
        instances = self._instances.get(provider_type, {})
        return sorted(instances.keys())

    def get_instance_config(
        self, provider_type: str, instance_name: str
    ) -> Optional[dict[str, Any]]:
        """

return instance parameter(${ENV} parse)

        Args:
            provider_type:Provider type
            instance_name:instancename

        Returns:
            parameterdictionary, or None(at)
        
"""
        instances = self._instances.get(provider_type)
        if instances is None:
            return None
        return instances.get(instance_name)

    def get_instance_config_redacted(
        self, provider_type: str, instance_name: str
    ) -> Optional[dict[str, Any]]:
        """


return instanceparameter(token/password etc.)

 Args:
 provider_type:Provider type
 instance_name:instancename

 Returns:
 parameterdictionary, or None
 
"""
        config = self.get_instance_config(provider_type, instance_name)
        if config is None:
            return None
        return _redact_config(config)

    def get_available_providers_summary(self) -> dict[str, list[str]]:
        """


return Provider type instancenamelist

 used for deps.extra["available_providers"].

 Returns:
 {provider_type:[instance_name,...]}
 
"""
        return {
            provider_type: self.list_instances(provider_type)
            for provider_type in self.list_providers()
        }

    def get_template(self, provider_type: str) -> Optional[ProviderTemplate]:
        """
get Provider template

        Args:
            provider_type:Provider type

        Returns:
            ProviderTemplate or None
        
"""
        return self._templates.get(provider_type)

    # ------------------------------------------------------------------
    # Skill register
    # ------------------------------------------------------------------

    def register_skills_to(self, skill_registry: "SkillRegistry") -> int:
        """

convert Provider Skills registerto Skill-Registry

        Provider Skill Handler Wrapper, implementinstance parse.
        Skill nameuse {provider_type}__{skill_name} for mat().

        Args:
            skill_registry:Skill-Registry

        Returns:
            register Skill count
        
"""
        from app.uniclaw.skills.registry import SkillMetadata

        total = 0
        for provider_type, template in self._templates.items():
            if not template.skills_dir.is_dir():
                logger.debug("Provider %s 无 skills/ 目录，跳过", provider_type)
                continue

            for py_file in sorted(template.skills_dir.glob("*.py")):
                if py_file.name.startswith("_") or py_file.stem == "shared":
                    continue

                try:
                    module = self._load_module(py_file)
                except Exception as e:
                    logger.warning("加载 Provider Skill %s 失败: %s", py_file, e)
                    continue

                skill_metadata_raw = getattr(module, "SKILL_METADATA", None)
                handler = getattr(module, "handler", None)

                if skill_metadata_raw is None or handler is None:
                    logger.debug("跳过 %s: 缺少 SKILL_METADATA 或 handler", py_file.name)
                    continue

                # build Provider Skill name:{provider}__{skill}
                original_name = (
                    skill_metadata_raw.name
                    if hasattr(skill_metadata_raw, "name")
                    else py_file.stem
                )
                prefixed_name = f"{provider_type}__{original_name}"

                # description
                description = (
                    skill_metadata_raw.description
                    if hasattr(skill_metadata_raw, "description")
                    else ""
                )

                # create SkillMetadata
                metadata = SkillMetadata(
                    name=prefixed_name,
                    description=description,
                    category=f"provider:{provider_type}",
                    provider_type=provider_type,
                    instance_required=True,
                    location="built-in",
                )

                # create Handler Wrapper
                wrapped = self._make_handler_wrapper(
                    handler=handler,
                    provider_type=provider_type,
                )

                skill_registry.register(metadata, wrapped)
                total += 1
                logger.debug("注册 Provider Skill: %s", prefixed_name)

        logger.info("共注册 %d 个 Provider Skills", total)
        return total

    # ------------------------------------------------------------------
    # Handler Wrapper
    # ------------------------------------------------------------------

    def _make_handler_wrapper(
        self,
        handler: Callable,
        provider_type: str,
    ) -> Callable:
        """


Handler Wrapper

 Wrapper:
 - if deps.extra["provider_instance"] → raw handler
 - if instance → instanceparameterto deps.extra
 - ifmulti instance → return LLM list_provider_instances

 Args:
 handler:raw Skill handler
 provider_type:Provider type

 Returns:
 handler
 
"""
        registry = self  # 

        @functools.wraps(handler)
        async def wrapper(ctx: Any, **kwargs: Any) -> Any:
            extra = ctx.deps.extra if hasattr(ctx, "deps") and hasattr(ctx.deps, "extra") else {}

            # instance
            if extra.get("provider_instance"):
                return await handler(ctx, **kwargs)

            # parse
            instances = registry.list_instances(provider_type)

            if len(instances) == 0:
                return {
                    "is_error": True,
                    "content": [{"type": "text", "text": f"Provider '{provider_type}' 没有配置任何实例"}],
                }

            if len(instances) == 1:
                # instance
                instance_name = instances[0]
                config = registry.get_instance_config(provider_type, instance_name)
                extra["provider_type"] = provider_type
                extra["provider_instance_name"] = instance_name
                extra["provider_instance"] = config or {}
                return await handler(ctx, **kwargs)

            # multiinstance
            return {
                "is_error": True,
                "content": [{
                    "type": "text",
                    "text": (
                        f"Provider '{provider_type}' 有 {len(instances)} 个实例: "
                        f"{', '.join(instances)}。"
                        f"请先调用 list_provider_instances(\"{provider_type}\") 查看可用实例，"
                        f"再调用 select_provider_instance 选择一个实例。"
                    ),
                }],
            }

        return wrapper

    # ------------------------------------------------------------------
    # 
    # ------------------------------------------------------------------

    @staticmethod
    def _find_provider_md(directory: Path) -> Optional[Path]:
        """

at Provider in MD

        PROVIDER.md,.md.

        Args:
            directory:Provider sub

        Returns:
            MD file path, or None
        
"""
        # PROVIDER.md
        provider_md = directory / "PROVIDER.md"
        if provider_md.is_file():
            return provider_md

        # MD
        named_md = directory / f"{directory.name}.md"
        if named_md.is_file():
            return named_md

        return None

    @staticmethod
    def _load_module(file_path: Path) -> Any:
        """

Python

        Args:
            file_path:.py file path

        Returns:
            
        
"""
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载模块: {file_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
