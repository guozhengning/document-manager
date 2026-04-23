from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import json

from src.utils.exceptions import ConfigError
from src.utils.models import AppSettings, ArchiveRule, DocTypeRule


# `__file__` 是当前文件 `src/workflow/config.py` 的路径。
# `resolve()` 会把它转成绝对路径，`parents[2]` 则回退两级，定位到项目根目录：
# `.../document manager/src/workflow/config.py` -> `.../document manager`
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 默认配置文件位置；如果调用 `load_settings()` 时没有传 `config_path`，就读取这里。
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.example.yaml"

# 默认环境变量候选路径。
# 读取顺序是先 `.env`，再 `.env.example`：
# `.env` 代表本机真实配置，`.env.example` 代表示例或兜底配置。
DEFAULT_ENV_PATHS = [PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.example"]


def load_settings(
    config_path: Path | None = None,
    env_path: Path | None = None,
) -> AppSettings:
    """读取配置文件和环境变量，构造运行配置对象。
    
    配置加载优先级：
    1. 系统环境变量（最高优先级）
    2. .env 文件中的环境变量
    3. YAML 配置文件中的值（最低优先级）
    
    Args:
        config_path: YAML 配置文件路径，未指定时使用默认路径
        env_path: 环境变量文件路径，未指定时尝试加载 .env 和 .env.example
        
    Returns:
        AppSettings: 包含所有配置参数的应用程序设置对象
        
    Raises:
        ConfigError: 当配置文件不存在或配置格式错误时抛出
    """
    # 先确定配置文件来源；未显式传入时，默认读取仓库里的示例配置。
    resolved_config_path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    if not resolved_config_path.is_file():
        raise ConfigError(f"配置文件不存在: {resolved_config_path}")

    # 加载 YAML 配置文件的基础数据
    settings_data = _load_yaml_config(resolved_config_path)
    
    # 环境变量用于覆盖 YAML，同一字段优先使用系统环境变量，其次是 .env / .env.example。
    env_values = _load_env_values(Path(env_path)) if env_path is not None else _load_default_env_values()

    try:
        # 先把配置按章节拆开，后续读取时能更明确地校验缺失位置。
        # 从配置数据中提取各个配置段：路径、解析器、AI、存储、日志
        paths = _require_mapping(settings_data, "paths")
        parser = _require_mapping(settings_data, "parser")
        ai = _require_mapping(settings_data, "ai")
        storage = _require_mapping(settings_data, "storage")
        logging_config = _require_mapping(settings_data, "logging")

        # 路径字段统一转成绝对 Path，避免后续模块再处理相对路径问题。
        # 使用 _coalesce_env 实现环境变量覆盖 YAML 配置的逻辑
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

        # 支持的扩展名统一标准化成小写集合，供扫描和解析模块直接使用。
        supported_extensions = {
            _normalize_extension(item)
            for item in _require_list(parser, "supported_extensions")
        }

        # 基础标量配置在这里完成类型校验，避免把脏数据带入运行时。
        # 布尔值、字符串、AI 提供商和模型名称等关键配置项
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
        raise  # 配置错误直接抛出，保留原始错误信息
    except Exception as exc:
        # 其他异常包装为 ConfigError，便于统一处理
        raise ConfigError(f"配置解析失败: {exc}") from exc

    # 返回统一的 AppSettings，后续流程只依赖这个对象，不再直接读原始配置字典。
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
    """按优先级尝试加载默认环境变量文件。
    
    遍历 DEFAULT_ENV_PATHS 中定义的环境变量文件路径，
    返回第一个存在的文件的环境变量键值对。
    
    Returns:
        dict[str, str]: 环境变量键值对字典，如果所有文件都不存在则返回空字典
    """
    for candidate in DEFAULT_ENV_PATHS:
        if candidate.is_file():
            return _load_env_values(candidate)
    return {}


def _load_env_values(env_path: Path) -> dict[str, str]:
    """从指定的环境变量文件中加载键值对。
    
    文件格式要求：
    - 每行一个环境变量，格式为 KEY=VALUE
    - 支持 # 注释行（会被跳过）
    - 空行会被跳过
    - VALUE 可以用单引号或双引号包裹，也可以不带引号
    
    Args:
        env_path: 环境变量文件路径
        
    Returns:
        dict[str, str]: 环境变量键值对字典
        
    Raises:
        ConfigError: 当文件不存在或格式错误时抛出
    """
    if not env_path.is_file():
        raise ConfigError(f"环境变量文件不存在: {env_path}")

    values: dict[str, str] = {}
    # 逐行读取并解析环境变量文件
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # 跳过空行和注释行
        if not line or line.startswith("#"):
            continue
        # 检查是否包含等号分隔符
        if "=" not in line:
            raise ConfigError(f"环境变量格式非法: {raw_line}")

        # 分割键值对，只分割第一个等号（值中可能包含等号）
        key, value = line.split("=", 1)
        key = key.strip()
        # 去除值两端的空白和引号
        value = value.strip().strip('"').strip("'")
        if not key:
            raise ConfigError(f"环境变量键为空: {raw_line}")
        values[key] = value
    return values


def _load_yaml_config(config_path: Path) -> dict[str, Any]:
    """加载并解析 YAML 配置文件。
    
    优先尝试使用 PyYAML 库进行解析，如果未安装则回退到内置的简单 YAML 解析器。
    
    Args:
        config_path: YAML 配置文件路径
        
    Returns:
        dict[str, Any]: 解析后的配置字典
        
    Raises:
        ConfigError: 当配置文件根节点不是字典时抛出
    """
    text = config_path.read_text(encoding="utf-8")

    # 优先使用 PyYAML 进行解析（功能更完整）
    try:
        import yaml  # type: ignore
    except ImportError:
        # 如果 PyYAML 未安装，回退到内置的简单 YAML 解析器
        return _parse_simple_yaml(text)
    try:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ConfigError("配置文件根节点必须是对象映射")
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML 解析错误: {exc}") from exc
    return data


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """简单的 YAML 解析器（不依赖 PyYAML 库）。
    
    支持基本的 YAML 语法：
    - 键值对（key: value）
    - 嵌套映射（通过缩进）
    - 列表（- 开头的行）
    - 注释（# 开头）
    - 标量类型自动推断（布尔、整数、浮点数、字符串）
    
    Args:
        text: YAML 文件内容字符串
        
    Returns:
        dict[str, Any]: 解析后的配置字典
        
    Raises:
        ConfigError: 当 YAML 格式错误或为空时抛出
    """
    # 预处理：去除注释行和空行，保留缩进信息
    prepared_lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        # 移除行内注释（# 后面的内容）
        line_without_comment = raw_line.split("#", 1)[0].rstrip()
        if not line_without_comment.strip():
            continue

        # 计算缩进级别
        indent = len(line_without_comment) - len(line_without_comment.lstrip(" "))
        prepared_lines.append((indent, line_without_comment.strip()))

    if not prepared_lines:
        raise ConfigError("配置文件为空")

    # 从第一行的缩进级别开始解析根节点
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
    """解析 YAML 代码块（映射或列表）。
    
    根据第一行的内容判断是映射还是列表，然后调用相应的解析函数。
     
    Args:
        lines: 预处理后的行列表，每项为 (缩进级别, 行内容)
        start_index: 开始解析的行索引
        indent: 当前代码块的缩进级别
        
    Returns:
        tuple[Any, int]: 解析结果和下一个待解析行的索引
        
    Raises:
        ConfigError: 当解析位置越界或缩进不合法时抛出
    """
    if start_index >= len(lines):
        raise ConfigError("YAML 解析位置越界")

    current_indent, current_text = lines[start_index]
    if current_indent != indent:
        raise ConfigError("YAML 缩进不合法")

    # 根据行首是否以 "- " 开头判断是列表还是映射
    if current_text.startswith("- "):
        return _parse_yaml_list(lines, start_index, indent)
    return _parse_yaml_mapping(lines, start_index, indent)


def _parse_yaml_mapping(
    lines: list[tuple[int, str]],
    start_index: int,
    indent: int,
) -> tuple[dict[str, Any], int]:
    """解析 YAML 映射（键值对）。
    
    逐行解析键值对，支持嵌套结构。如果值为空，则尝试解析下一行的嵌套代码块。
    
    Args:
        lines: 预处理后的行列表
        start_index: 开始解析的行索引
        indent: 当前映射的缩进级别
        
    Returns:
        tuple[dict[str, Any], int]: 解析后的字典和下一个待解析行的索引
        
    Raises:
        ConfigError: 当映射格式或缩进不合法时抛出
    """
    result: dict[str, Any] = {}
    index = start_index

    while index < len(lines):
        current_indent, current_text = lines[index]
        # 缩进小于当前级别，说明映射结束
        if current_indent < indent:
            break
        if current_indent > indent: 
            raise ConfigError("YAML 映射缩进不合法")
        if current_text.startswith("- "):
            raise ConfigError("YAML 映射中出现非法列表项")
        if ":" not in current_text:
            raise ConfigError(f"YAML 映射格式非法: {current_text}")

        # 分割键值对
        key, raw_value = current_text.split(":", 1)
        key = key.strip()
        value_text = raw_value.strip()
        if not key:
            raise ConfigError("YAML 键不能为空")

        if value_text:
            # 值不为空，直接解析标量值
            result[key] = _coerce_scalar(value_text)
            index += 1
            continue

        # 值为空，可能有嵌套结构
        index += 1
        if index >= len(lines) or lines[index][0] <= indent:
            # 下一行缩进级别不深，说明值为空字典
            result[key] = {}
            continue

        # 解析嵌套的代码块
        nested_value, index = _parse_yaml_block(lines, index, lines[index][0])
        result[key] = nested_value

    return result, index


def _parse_yaml_list(
    lines: list[tuple[int, str]],
    start_index: int,
    indent: int,
) -> tuple[list[Any], int]:
    """解析 YAML 列表。
    
    逐行解析列表项，支持嵌套结构。列表项以 "- " 开头。
    
    Args:
        lines: 预处理后的行列表
        start_index: 开始解析的行索引
        indent: 当前列表的缩进级别
        
    Returns:
        tuple[list[Any], int]: 解析后的列表和下一个待解析行的索引
        
    Raises:
        ConfigError: 当列表格式或缩进不合法时抛出
    """
    result: list[Any] = []
    index = start_index

    while index < len(lines):
        current_indent, current_text = lines[index]
        # 缩进小于当前级别，说明列表结束
        if current_indent < indent:
            break
        if current_indent != indent or not current_text.startswith("- "):
            raise ConfigError("YAML 列表缩进不合法")

        # 提取列表项内容（去掉 "- " 前缀）
        item_text = current_text[2:].strip()
        if item_text:
            # 项不为空，直接解析标量值
            result.append(_coerce_scalar(item_text))
            index += 1
            continue

        # 项为空，可能有嵌套结构
        index += 1
        if index >= len(lines) or lines[index][0] <= indent:
            # 下一行缩进级别不深，说明项值为 None
            result.append(None)
            continue

        # 解析嵌套的代码块
        nested_value, index = _parse_yaml_block(lines, index, lines[index][0])
        result.append(nested_value)

    return result, index


def _coerce_scalar(value: str) -> Any:
    """将字符串自动推断并转换为合适的标量类型。
    
    类型推断顺序：
    1. 布尔值：true/false（不区分大小写）
    2. 整数：纯数字或以 - 开头的数字
    3. 浮点数：包含小数点的数字
    4. 字符串：去除两端引号
    
    Args:
        value: 待转换的字符串值
        
    Returns:
        Any: 转换后的标量值（bool、int、float 或 str）
    """
    lower_value = value.lower()
    # 布尔值转换
    if lower_value == "true":
        return True
    if lower_value == "false":
        return False

    # 整数转换
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)

    # 浮点数转换
    try:
        if "." in value:
            return float(value)
    except ValueError:
        pass

    # 字符串：去除两端引号
    return value.strip('"').strip("'")


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    """从配置字典中获取指定的映射（字典）类型配置段。
    
    Args:
        data: 配置字典
        key: 配置段键名
        
    Returns:
        dict[str, Any]: 配置段的字典值
        
    Raises:
        ConfigError: 当配置段缺失或格式非法时抛出
    """
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"配置段缺失或格式非法: {key}")
    return value


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    """从配置字典中获取指定的列表类型配置项。
    
    Args:
        data: 配置字典
        key: 配置项键名
        
    Returns:
        list[Any]: 配置项的列表值
        
    Raises:
        ConfigError: 当配置项缺失或不是列表时抛出
    """
    value = data.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"配置项缺失或不是列表: {key}")
    return value


def _require_string(value: Any, field_name: str) -> str:
    """验证并返回非空字符串。
    
    Args:
        value: 待验证的值
        field_name: 字段名称（用于错误信息）
        
    Returns:
        str: 去除两端空白后的字符串
        
    Raises:
        ConfigError: 当值缺失或为空字符串时抛出
    """
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"配置项缺失或为空: {field_name}")
    return value.strip()


def _parse_bool(value: Any) -> bool:
    """将配置值解析为布尔类型。
    
    支持的值格式：
    - True: 1, "true", "yes", "on"（不区分大小写）
    - False: 0, "false", "no", "off"（不区分大小写）
    
    Args:
        value: 待解析的配置值
        
    Returns:
        bool: 解析后的布尔值
        
    Raises:
        ConfigError: 当值无法解析为布尔值时抛出
    """
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
    """标准化文件扩展名（确保以 '.' 开头并转为小写）。
    
    Args:
        value: 待标准化的扩展名值
        
    Returns:
        str: 标准化后的扩展名（小写，以 '.' 开头）
        
    Raises:
        ConfigError: 当值缺失或不是以 '.' 开头时抛出
    """
    extension = _require_string(value, field_name="parser.supported_extensions")
    if not extension.startswith("."):
        raise ConfigError(f"扩展名必须以 '.' 开头: {extension}")
    return extension.lower()


def _resolve_path(value: Any) -> Path:
    """将路径值解析为 Path 对象，如果是相对路径则转为绝对路径。
    
    Args:
        value: 待解析的路径值（可以是字符串或 Path）
        
    Returns:
        Path: 解析后的路径对象（绝对路径）
    """
    path_value = _require_string(value, field_name="path")
    path = Path(path_value)
    # 如果是相对路径，则相对于项目根目录解析
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _coalesce_env(env_values: dict[str, str], key: str, fallback: Any) -> Any:
    """按优先级获取配置值：系统环境变量 > .env 文件 > YAML 配置。
    
    配置值查找顺序：
    1. 系统环境变量（最高优先级）
    2. .env 文件中的环境变量
    3. YAML 配置文件中的默认值（最低优先级）
    
    Args:
        env_values: .env 文件中的环境变量键值对
        key: 配置项键名
        fallback: YAML 配置中的默认值
        
    Returns:
        Any: 找到的第一个有效值，如果都不存在则返回 fallback
    """
    return os.environ.get(key, env_values.get(key, fallback))


def load_rules(rules_path: Path) -> tuple[list[DocTypeRule], list[ArchiveRule]]:
    """
    加载文档类型规则和归档规则。

    doc_type_rules 和 archive_rules 解析后保持定义顺序。规则缺少关键字段时直接失败，不做静默容错。

    Args:
        rules_path: 规则文件路径

    Returns:
        tuple: 包含文档类型规则列表和归档规则列表的元组  
    """
    if not rules_path.is_file():
        raise ConfigError(f"规则文件不存在: {rules_path}")
    
    try:
        rules_data = json.loads(rules_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"规则文件 JSON 解析错误: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"规则文件读取失败: {exc}") from exc
    if not isinstance(rules_data, dict):
        raise ConfigError("规则文件根节点必须是对象")

    if not isinstance(rules_data.get("doc_type_rules"), list):
        raise ConfigError("doc_type_rules 必须是列表")

    if not isinstance(rules_data.get("archive_rules"), list):
        raise ConfigError("archive_rules 必须是列表")

    try:
        doc_type_rules = []
        for item in rules_data["doc_type_rules"]:
            if not isinstance(item, dict):
                raise ConfigError("doc_type_rules 中的每项必须是对象")
            if not isinstance(item.get("name"), str) or not item["name"].strip():
                raise ConfigError("doc_type_rules 中的每项必须包含非空字符串字段 name")
            if not isinstance(item.get("keywords"), list) or not all(isinstance(k, str) and k.strip() for k in item["keywords"]):
                raise ConfigError("doc_type_rules 中的每项必须包含字符串列表字段 keywords")
            doc_type_rules.append(DocTypeRule(name=item["name"].strip(), keywords=[k.strip() for k in item["keywords"]]))

        archive_rules = []
        for item in rules_data["archive_rules"]:
            if not isinstance(item, dict):
                raise ConfigError("archive_rules 中的每项必须是对象")
            if not isinstance(item.get("doc_type"), str) or not item["doc_type"].strip():
                raise ConfigError("archive_rules 中的每项必须包含非空字符串字段 doc_type")
            if not isinstance(item.get("target_folder"), str) or not item["target_folder"].strip():
                raise ConfigError("archive_rules 中的每项必须包含非空字符串字段 target_folder")
            archive_rules.append(ArchiveRule(doc_type=item["doc_type"].strip(), target_folder=item["target_folder"].strip()))
    except KeyError as exc:
        raise ConfigError(f"规则项缺少必要字段: {exc}") from exc
    return doc_type_rules, archive_rules         


    










