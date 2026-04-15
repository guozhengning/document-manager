from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.utils.exceptions import ConfigError
from src.utils.models import AppSettings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.example.yaml"
DEFAULT_ENV_PATHS = [PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.example"]


def load_settings(
    config_path: Path | None = None,
    env_path: Path | None = None,
) -> AppSettings:
    """读取配置文件和环境变量，构造运行配置对象。"""
    resolved_config_path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    if not resolved_config_path.is_file():
        raise ConfigError(f"配置文件不存在: {resolved_config_path}")

    settings_data = _load_yaml_config(resolved_config_path)
    env_values = _load_env_values(Path(env_path)) if env_path is not None else _load_default_env_values()

    try:
        paths = _require_mapping(settings_data, "paths")
        parser = _require_mapping(settings_data, "parser")
        ai = _require_mapping(settings_data, "ai")
        storage = _require_mapping(settings_data, "storage")
        logging_config = _require_mapping(settings_data, "logging")

        watch_directory = _resolve_path(
            _coalesce_env(env_values, "WATCH_DIRECTORY", paths.get("watch_directory")),
        )
        result_directory = _resolve_path(
            _coalesce_env(env_values, "RESULT_DIRECTORY", paths.get("result_directory")),
        )
        archive_directory = _resolve_path(
            _coalesce_env(env_values, "ARCHIVE_DIRECTORY", paths.get("archive_directory")),
        )
        temp_directory = _resolve_path(
            _coalesce_env(env_values, "TEMP_DIRECTORY", paths.get("temp_directory")),
        )
        log_directory = _resolve_path(
            _coalesce_env(env_values, "LOG_DIRECTORY", paths.get("log_directory")),
        )
        prompt_file = _resolve_path(
            _coalesce_env(env_values, "PROMPT_FILE", ai.get("prompt_file")),
        )

        supported_extensions = {
            _normalize_extension(item)
            for item in _require_list(parser, "supported_extensions")
        }

        overwrite_existing = _parse_bool(
            _coalesce_env(env_values, "OVERWRITE_EXISTING", storage.get("overwrite_existing")),
        )
        log_level = _require_string(
            _coalesce_env(env_values, "LOG_LEVEL", logging_config.get("level")),
            field_name="logging.level",
        )
        ai_provider = _require_string(
            _coalesce_env(env_values, "LLM_PROVIDER", ai.get("provider")),
            field_name="ai.provider",
        )
        ai_model = _require_string(
            _coalesce_env(env_values, "LLM_MODEL", ai.get("model")),
            field_name="ai.model",
        )
    except ConfigError:
        raise
    except Exception as exc:
        raise ConfigError(f"配置解析失败: {exc}") from exc

    return AppSettings(
        watch_directory=watch_directory,
        result_directory=result_directory,
        archive_directory=archive_directory,
        temp_directory=temp_directory,
        log_directory=log_directory,
        prompt_file=prompt_file,
        supported_extensions=supported_extensions,
        overwrite_existing=overwrite_existing,
        log_level=log_level,
        ai_provider=ai_provider,
        ai_model=ai_model,
    )


def _load_default_env_values() -> dict[str, str]:
    for candidate in DEFAULT_ENV_PATHS:
        if candidate.is_file():
            return _load_env_values(candidate)
    return {}


def _load_env_values(env_path: Path) -> dict[str, str]:
    if not env_path.is_file():
        raise ConfigError(f"环境变量文件不存在: {env_path}")

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f"环境变量格式非法: {raw_line}")

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            raise ConfigError(f"环境变量键为空: {raw_line}")
        values[key] = value
    return values


def _load_yaml_config(config_path: Path) -> dict[str, Any]:
    text = config_path.read_text(encoding="utf-8")

    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_simple_yaml(text)

    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ConfigError("配置文件根节点必须是对象映射")
    return data


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    prepared_lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        line_without_comment = raw_line.split("#", 1)[0].rstrip()
        if not line_without_comment.strip():
            continue

        indent = len(line_without_comment) - len(line_without_comment.lstrip(" "))
        prepared_lines.append((indent, line_without_comment.strip()))

    if not prepared_lines:
        raise ConfigError("配置文件为空")

    parsed, next_index = _parse_yaml_block(prepared_lines, 0, prepared_lines[0][0])
    if next_index != len(prepared_lines):
        raise ConfigError("配置文件存在未解析内容")
    if not isinstance(parsed, dict):
        raise ConfigError("配置文件根节点必须是对象映射")
    return parsed


def _parse_yaml_block(
    lines: list[tuple[int, str]],
    start_index: int,
    indent: int,
) -> tuple[Any, int]:
    if start_index >= len(lines):
        raise ConfigError("YAML 解析位置越界")

    current_indent, current_text = lines[start_index]
    if current_indent != indent:
        raise ConfigError("YAML 缩进不合法")

    if current_text.startswith("- "):
        return _parse_yaml_list(lines, start_index, indent)
    return _parse_yaml_mapping(lines, start_index, indent)


def _parse_yaml_mapping(
    lines: list[tuple[int, str]],
    start_index: int,
    indent: int,
) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    index = start_index

    while index < len(lines):
        current_indent, current_text = lines[index]
        if current_indent < indent:
            break
        if current_indent != indent:
            raise ConfigError("YAML 映射缩进不合法")
        if current_text.startswith("- "):
            raise ConfigError("YAML 映射中出现非法列表项")
        if ":" not in current_text:
            raise ConfigError(f"YAML 映射格式非法: {current_text}")

        key, raw_value = current_text.split(":", 1)
        key = key.strip()
        value_text = raw_value.strip()
        if not key:
            raise ConfigError("YAML 键不能为空")

        if value_text:
            result[key] = _coerce_scalar(value_text)
            index += 1
            continue

        index += 1
        if index >= len(lines) or lines[index][0] <= indent:
            result[key] = {}
            continue

        nested_value, index = _parse_yaml_block(lines, index, lines[index][0])
        result[key] = nested_value

    return result, index


def _parse_yaml_list(
    lines: list[tuple[int, str]],
    start_index: int,
    indent: int,
) -> tuple[list[Any], int]:
    result: list[Any] = []
    index = start_index

    while index < len(lines):
        current_indent, current_text = lines[index]
        if current_indent < indent:
            break
        if current_indent != indent or not current_text.startswith("- "):
            raise ConfigError("YAML 列表缩进不合法")

        item_text = current_text[2:].strip()
        if item_text:
            result.append(_coerce_scalar(item_text))
            index += 1
            continue

        index += 1
        if index >= len(lines) or lines[index][0] <= indent:
            result.append(None)
            continue

        nested_value, index = _parse_yaml_block(lines, index, lines[index][0])
        result.append(nested_value)

    return result, index


def _coerce_scalar(value: str) -> Any:
    lower_value = value.lower()
    if lower_value == "true":
        return True
    if lower_value == "false":
        return False

    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)

    try:
        if "." in value:
            return float(value)
    except ValueError:
        pass

    return value.strip('"').strip("'")


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"配置段缺失或格式非法: {key}")
    return value


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"配置项缺失或不是列表: {key}")
    return value


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"配置项缺失或为空: {field_name}")
    return value.strip()


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ConfigError(f"布尔配置非法: {value!r}")


def _normalize_extension(value: Any) -> str:
    extension = _require_string(value, field_name="parser.supported_extensions")
    if not extension.startswith("."):
        raise ConfigError(f"扩展名必须以 '.' 开头: {extension}")
    return extension.lower()


def _resolve_path(value: Any) -> Path:
    path_value = _require_string(value, field_name="path")
    path = Path(path_value)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _coalesce_env(env_values: dict[str, str], key: str, fallback: Any) -> Any:
    return os.environ.get(key, env_values.get(key, fallback))
