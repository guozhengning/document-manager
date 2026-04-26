# 详细设计文档 - Document Manager V1

## 1. 文档信息

- 文档版本：`v1.0`
- 作者：`me`
- 日期：`2026-04-14`
- 适用版本：`第一版最小可运行闭环`
- 关联文档：
  - [README.md](C:\Users\lenovo\Desktop\document manager\README.md)
  - [workflow.md](C:\Users\lenovo\Desktop\document manager\workflow.md)
  - [docs/first_version_interface.md](C:\Users\lenovo\Desktop\document manager\docs\first_version_interface.md)
  - [tests/cases/manual_test_cases.md](C:\Users\lenovo\Desktop\document manager\tests\cases\manual_test_cases.md)

## 2. 设计目标与范围

### 2.1 设计目标

- 完成 `.txt` 文档的单次处理闭环。
- 支持扫描、解析、AI/Mock 分析、规则修正、结果落盘、原文件归档、日志记录。
- 固化模块职责、数据结构、接口边界和错误处理规则，降低实现阶段的二次设计成本。

### 2.2 本版包含

- 配置加载与规则加载
- 目录初始化检查
- 手动单次执行 `run_once`
- `data/inbox` 目录扫描
- `.txt` 文本解析
- Mock AI 分析
- 规则匹配与结果修正
- JSON 结果输出
- 原文件归档
- 本地文本日志

### 2.3 本版不包含

- 目录持续监听 `run_watcher_loop`
- `.pdf` / `.docx` 正式解析
- 真实在线模型调用
- 数据库
- Web 页面
- 并发处理

## 3. 整体架构与主流程

### 3.1 模块划分

- `src/workflow`：启动、配置、流程编排
- `src/watcher`：目录扫描与任务生成
- `src/parser`：文档解析与文本清洗
- `src/ai`：Prompt 装配与文档分析
- `src/storage`：规则修正、结果保存、归档、日志
- `src/utils`：公共模型与异常定义

### 3.2 主流程

```text
main.py
  -> load_settings()
  -> load_rules()
  -> bootstrap_app()
  -> run_once()
       -> scan_inbox()
       -> process_document(job)
            -> parse_document()
            -> analyze_document()
            -> match_doc_type()
            -> resolve_archive_folder()
            -> resolve_suggested_name()
            -> merge_ai_and_rules()
            -> build_result_record()
            -> save_result()
            -> archive_original_file()
            -> write_processing_log()
```

### 3.3 设计原则

- 第一版优先保证闭环稳定，不追求功能广度。
- 各模块通过标准数据对象交互，不直接透传零散字段。
- 单文件失败不影响批次内其他文件。
- 为后续扩展 `pdf/docx` 和真实 LLM 预留稳定接口。

## 4. 模块设计

### 4.1 `src/workflow`

- 职责：流程编排、配置加载、启动校验。
- 输入：配置文件、规则文件、待处理任务。
- 输出：处理记录、运行状态。
- 不负责：具体解析实现、AI 推理细节、落盘细节。

### 4.2 `src/watcher`

- 职责：扫描 `data/inbox` 并生成 `FileJob`。
- 输入：目录路径、支持格式列表。
- 输出：按稳定顺序排列的任务列表。

### 4.3 `src/parser`

- 职责：根据文件类型读取文档内容并统一产出 `ParseResult`。
- 输入：原始文件路径。
- 输出：标准解析结果。

### 4.4 `src/ai`

- 职责：读取 Prompt、组装模型输入、输出统一 `AIResult`。
- 输入：`ParseResult`、Prompt 模板、运行配置。
- 输出：`AIResult`。

### 4.5 `src/storage`

- 职责：规则修正、结果保存、原文件归档、日志写入。
- 输入：AI 结果、规则、路径信息。
- 输出：结果 JSON、归档路径、日志记录。

### 4.6 `src/utils`

- 职责：公共数据模型、异常类型、跨模块通用约束。
- 输入：各模块公共依赖。
- 输出：统一类型和异常边界。

## 5. 数据结构设计

以下类型建议定义在 `src/utils/models.py`。

### 5.1 `AppSettings`

```python
@dataclass(slots=True)
class AppSettings:
    watch_directory: Path
    result_directory: Path
    archive_directory: Path
    temp_directory: Path
    log_directory: Path
    prompt_file: Path
    supported_extensions: set[str]
    overwrite_existing: bool
    log_level: str
    ai_provider: str
    ai_model: str
```

字段说明：

- `watch_directory`：待处理目录。
- `result_directory`：结果 JSON 输出目录。
- `archive_directory`：原文件归档根目录。
- `temp_directory`：临时文件目录。
- `log_directory`：日志输出目录。
- `prompt_file`：Prompt 模板路径。
- `supported_extensions`：允许扫描的扩展名集合，统一使用小写。
- `overwrite_existing`：结果文件是否允许覆盖。
- `log_level`：日志级别。
- `ai_provider`：AI 提供方标识。
- `ai_model`：模型名或 Mock 通道标识。

### 5.2 `FileJob`

```python
@dataclass(slots=True)
class FileJob:
    job_id: str
    file_path: Path
    file_name: str
    extension: str
    status: str = "pending"
```

规则：

- `job_id` 必须全局唯一，建议包含日期和序号。
- `extension` 统一小写，格式如 `.txt`。
- `status` 初始值为 `pending`。

### 5.3 `ParseResult`

```python
@dataclass(slots=True)
class ParseResult:
    file_name: str
    file_path: str
    extension: str
    raw_text: str
    clean_text: str
    metadata: dict[str, Any]
```

规则：

- `raw_text` 保留原始读取结果。
- `clean_text` 用于 AI 和规则匹配。
- `metadata` 可扩展记录编码、大小、页数等附加信息。

### 5.4 `AIResult`

```python
@dataclass(slots=True)
class AIResult:
    file_name: str
    file_path: str
    doc_type: str
    summary: str
    keywords: list[str]
    suggested_folder: str
    suggested_name: str
    confidence: float
```

规则：

- `confidence` 范围固定为 `0~1`。
- 信息不足时必须显式输出 `doc_type="待确认"`。
- `keywords` 默认去重，保留稳定顺序。

### 5.5 `FinalRecord`

```python
@dataclass(slots=True)
class FinalRecord:
    job_id: str
    source_file: str
    status: str
    doc_type: str
    summary: str
    keywords: list[str]
    suggested_folder: str
    suggested_name: str
    confidence: float
    result_file: str | None
    archive_file: str | None
    error_message: str | None
```

状态约定：

- `done`：处理成功并完成落盘、归档。
- `failed`：处理失败。
- `skipped`：被显式跳过。

### 5.6 `DocTypeRule`

```python
@dataclass(slots=True)
class DocTypeRule:
    name: str
    keywords: list[str]
```

### 5.7 `ArchiveRule`

```python
@dataclass(slots=True)
class ArchiveRule:
    doc_type: str
    target_folder: str
```

## 6. 异常设计

以下异常建议定义在 `src/utils/exceptions.py`。

```python
class ConfigError(Exception): ...
class UnsupportedFileError(Exception): ...
class ParseError(Exception): ...
class AIError(Exception): ...
class StorageError(Exception): ...
```

异常约定：

- `ConfigError`：配置缺失、字段非法、目录初始化失败。
- `UnsupportedFileError`：文件扩展名不在支持列表中。
- `ParseError`：文本读取失败、编码异常、清洗后文本为空。
- `AIError`：Prompt 模板读取失败、Mock 分析异常、后续模型调用异常。
- `StorageError`：结果写入失败、归档失败、日志写入失败。

## 7. 接口设计

本节固定关键函数的职责、输入输出和异常边界。

### 7.1 配置与初始化

#### `load_settings(config_path: Path | None = None, env_path: Path | None = None) -> AppSettings`

- 模块路径：`src/workflow/config.py`
- 作用：读取 YAML 和环境变量，构造运行配置对象。
- 输入：
  - `config_path`：配置文件路径，可为空。
  - `env_path`：环境变量文件路径，可为空。
- 输出：`AppSettings`
- 异常：配置缺失或字段非法时抛 `ConfigError`
- 调用时机：程序启动阶段
- 处理规则：
  - 使用默认示例路径作为兜底。
  - 所有目录路径转为 `Path` 对象。
  - `supported_extensions` 统一转为小写集合。

#### `load_rules(rules_path: Path) -> tuple[list[DocTypeRule], list[ArchiveRule]]`

- 模块路径：`src/workflow/config.py`
- 作用：加载文档类型规则和归档规则。
- 输入：`rules_path`
- 输出：`(doc_type_rules, archive_rules)`
- 异常：JSON 非法或字段缺失时抛 `ConfigError`
- 调用时机：程序启动阶段
- 处理规则：
  - `doc_type_rules` 和 `archive_rules` 解析后保持定义顺序。
  - 规则缺少关键字段时直接失败，不做静默容错。

#### `bootstrap_app(settings: AppSettings) -> None`

- 模块路径：`src/workflow/runner.py`
- 作用：检查目录、Prompt 文件和基础运行条件。
- 输入：`settings`
- 输出：`None`
- 异常：目录不可用或 Prompt 缺失时抛 `ConfigError`
- 调用时机：`run_once()` 前
- 处理规则：
  - `watch_directory`不存在或不是目录时报错
  - `result_directory`、`archive_directory`、`temp_directory`、`log_directory` 不存在时自动创建。
。
  - `prompt_file` 不存在或不是文件时直接报错。

### 7.2 扫描与任务生成

#### `scan_inbox(watch_dir: Path, supported_extensions: set[str]) -> list[FileJob]`

- 模块路径：`src/watcher/scanner.py`
- 作用：扫描输入目录并生成待处理任务列表。
- 输入：
  - `watch_dir`：待扫描目录
  - `supported_extensions`：支持后缀集合
- 输出：`list[FileJob]`
- 异常：目录不可读时抛 `ConfigError`
- 调用时机：`run_once()` 开始阶段
- 处理规则：
  - 仅处理普通文件。
  - 后缀统一转小写。
  - 按文件名排序。
  - 第一版只允许返回 `.txt`。

#### `filter_supported_files(file_paths: list[Path], supported_extensions: set[str]) -> list[Path]`

- 模块路径：`src/watcher/scanner.py`
- 作用：过滤支持的后缀名。
- 输入：路径列表、支持后缀集合。
- 输出：过滤后的路径列表。
- 异常：无
- 调用时机：`scan_inbox()` 内部
- 处理规则：
  - 非文件项直接剔除。
  - 扩展名比较按小写处理。

### 7.3 文档解析

#### `detect_file_extension(file_path: Path) -> str`

- 模块路径：`src/parser/core.py`
- 作用：提取并规范化扩展名。
- 输入：`file_path`
- 输出：如 `.txt`
- 异常：无扩展名时抛 `UnsupportedFileError`
- 调用时机：`parse_document()` 内部
- 处理规则：返回值必须以 `.` 开头且为小写。

#### `parse_document(file_path: Path) -> ParseResult`

- 模块路径：`src/parser/core.py`
- 作用：根据扩展名分发到具体解析器。
- 输入：`file_path`
- 输出：`ParseResult`
- 异常：不支持的格式抛 `UnsupportedFileError`
- 调用时机：`process_document()` 内部
- 处理规则：
  - 第一版仅支持 `.txt`
  - 其他格式直接失败，不做兜底解析

#### `parse_txt(file_path: Path) -> ParseResult`

- 模块路径：`src/parser/txt_parser.py`
- 作用：读取文本文件并构造标准解析结果。
- 输入：`file_path`
- 输出：`ParseResult`
- 异常：读取失败或编码异常时抛 `ParseError`
- 调用时机：`.txt` 文件解析阶段
- 处理规则：
  - 支持常见编码读取。
  - 原始文本保留在 `raw_text`。
  - 清洗结果为空时抛 `ParseError`。

#### `clean_extracted_text(text: str) -> str`

- 模块路径：`src/parser/common.py`
- 作用：清洗文本，去掉多余空白和连续空行。
- 输入：原始文本
- 输出：清洗后的文本
- 异常：无
- 调用时机：构造 `ParseResult` 前
- 处理规则：
  - 合并连续空白。
  - 保留必要段落边界。

#### `build_parse_result(file_path: Path, raw_text: str, metadata: dict[str, Any] | None = None) -> ParseResult`

- 模块路径：`src/parser/common.py`
- 作用：统一封装解析结果。
- 输入：原文件路径、文本、元信息。
- 输出：`ParseResult`
- 异常：清洗后文本为空时抛 `ParseError`
- 调用时机：各解析器内部
- 处理规则：
  - `metadata` 为空时使用空字典。
  - `file_path` 序列化为字符串。

### 7.4 AI 分析

#### `load_prompt_template(prompt_file: Path) -> str`

- 模块路径：`src/ai/prompting.py`
- 作用：读取 Prompt 模板文件。
- 输入：`prompt_file`
- 输出：模板字符串
- 异常：文件不可读时抛 `AIError`
- 调用时机：`analyze_document()` 内部
- 处理规则：第一版不缓存，按调用读取。

#### `build_ai_input(parse_result: ParseResult, prompt_template: str) -> str`

- 模块路径：`src/ai/prompting.py`
- 作用：拼接模型输入文本。
- 输入：`parse_result`、`prompt_template`
- 输出：最终提示词文本
- 异常：无
- 调用时机：调用分析器前
- 处理规则：
  - 至少包含文件名、路径、清洗后文本。
  - 不直接拼接无关元数据。

#### `analyze_document(parse_result: ParseResult, settings: AppSettings) -> AIResult`

- 模块路径：`src/ai/analyzer.py`
- 作用：对解析结果做分类与摘要。
- 输入：`parse_result`、`settings`
- 输出：`AIResult`
- 异常：Prompt 读取失败或分析过程异常时抛 `AIError`
- 调用时机：`process_document()` 内部
- 处理规则：
  - 第一版优先读取 Prompt 模板。
  - 默认走本地 `mock_analyze_document()`。
  - 为后续真实模型调用保留同名接口。

#### `mock_analyze_document(parse_result: ParseResult, ai_input) -> AIResult`

- 模块路径：`src/ai/analyzer.py`
- 作用：第一版的占位实现，用关键词和截断文本生成结果。
- 输入：`parse_result`, `ai_input`:第一版只接受不使用
- 输出：`AIResult`
- 异常：无
- 调用时机：`analyze_document()` 内部
- 处理规则：
  - 包含“合同”“协议”时输出 `doc_type="合同"`
  - 包含“发票”“税额”时输出 `doc_type="发票"`
  - 否则输出 `doc_type="待确认"`
  - `summary` 截取前 `80~120` 个字符
  - `keywords` 由命中词和高频词组成简化版本

### 7.5 规则与结果修正

#### `match_doc_type(text: str, ai_result: AIResult, rules: list[DocTypeRule]) -> str`

- 模块路径：`src/storage/rules.py`
- 作用：根据规则修正最终文档类型。
- 输入：文本、AI 结果、规则列表。
- 输出：最终 `doc_type`
- 异常：无
- 调用时机：AI 分析后
- 处理规则：
  - 规则命中优先级高于 AI 建议。
  - 多条规则命中时按定义顺序取第一条。
  - 未命中时保留 AI 输出。

#### `resolve_archive_folder(doc_type: str, rules: list[ArchiveRule]) -> str`

- 模块路径：`src/storage/rules.py`
- 作用：根据文档类型决定归档目录。
- 输入：`doc_type`、归档规则。
- 输出：目标目录字符串。
- 异常：无
- 调用时机：文档类型确认后
- 处理规则：
  - 命中规则时返回对应目录。
  - 未命中时使用兜底值 `待分类/待确认`。

#### `resolve_suggested_name(ai_result: AIResult, source_path: Path) -> str`

- 模块路径：`src/storage/rules.py`
- 作用：生成建议文件名。
- 输入：`ai_result`、源文件路径。
- 输出：建议文件名。
- 异常：无
- 调用时机：归档前
- 处理规则：
  - 优先使用 `ai_result.suggested_name`
  - 缺失或空字符串时使用原文件名

#### `merge_ai_and_rules(ai_result: AIResult, resolved_doc_type: str, resolved_folder: str, suggested_name: str) -> AIResult`

- 模块路径：`src/storage/rules.py`
- 作用：将规则结果覆盖回标准输出对象。
- 输入：AI 结果、规则决策结果。
- 输出：修正后的 `AIResult`
- 异常：无
- 调用时机：落盘前
- 处理规则：只覆盖最终分类、目录和建议名称，不重算摘要和关键词。

### 7.6 结果落盘

#### `build_result_record(job: FileJob, parse_result: ParseResult, ai_result: AIResult, result_file: Path | None = None, archive_file: Path | None = None, status: str = "done", error_message: str | None = None) -> FinalRecord`

- 模块路径：`src/storage/results.py`
- 作用：构建最终结果对象。
- 输入：任务、解析结果、AI 结果及可选路径。
- 输出：`FinalRecord`
- 异常：无
- 调用时机：处理成功或失败收口阶段
- 处理规则：
  - 路径字段在落盘前允许为空。
  - 失败记录必须带 `error_message`。

#### `save_result(record: FinalRecord, result_dir: Path, overwrite: bool = False) -> Path`

- 模块路径：`src/storage/results.py`
- 作用：将结果写入 JSON 文件。
- 输入：`record`、结果目录、是否允许覆盖。
- 输出：结果文件路径。
- 异常：写入失败时抛 `StorageError`
- 调用时机：生成 `FinalRecord` 后
- 处理规则：
  - 文件命名建议：`<job_id>.json`
  - 默认不覆盖已有文件

#### `result_exists(result_path: Path) -> bool`

- 模块路径：`src/storage/results.py`
- 作用：判断结果文件是否已存在。
- 输入：结果路径
- 输出：`bool`
- 异常：无
- 调用时机：`save_result()` 内部

### 7.7 归档处理

#### `ensure_archive_path(archive_root: Path, target_folder: str) -> Path`

- 模块路径：`src/storage/archive.py`
- 作用：确保归档目录存在。
- 输入：归档根目录、目标子目录。
- 输出：归档目录路径。
- 异常：目录不可创建时抛 `StorageError`
- 调用时机：归档前
- 处理规则：目标目录按相对路径拼接到 `archive_root` 下。

#### `handle_name_conflict(target_path: Path) -> Path`

- 模块路径：`src/storage/archive.py`
- 作用：处理重名文件。
- 输入：目标路径
- 输出：可安全写入的新路径
- 异常：无
- 调用时机：移动原文件前
- 处理规则：文件名后追加时间戳或序号。

#### `archive_original_file(file_path: Path, archive_root: Path, target_folder: str) -> Path`

- 模块路径：`src/storage/archive.py`
- 作用：归档原始输入文件。
- 输入：原文件、归档根目录、目标子目录。
- 输出：最终归档文件路径。
- 异常：移动失败时抛 `StorageError`
- 调用时机：结果 JSON 写入后
- 处理规则：
  - 先确保归档目录存在。
  - 重名时走冲突处理逻辑。

### 7.8 日志

#### `write_processing_log(level: str, message: str, context: dict[str, Any] | None = None) -> None`

- 模块路径：`src/storage/logging_service.py`
- 作用：写入处理日志。
- 输入：级别、消息、上下文。
- 输出：`None`
- 异常：写入失败时抛 `StorageError`
- 调用时机：成功和失败路径都可调用
- 处理规则：
  - 第一版至少落本地文本日志。
  - 上下文中避免记录敏感全文。

#### `write_error_log(job: FileJob, error: Exception) -> None`

- 模块路径：`src/storage/logging_service.py`
- 作用：记录失败任务和错误信息。
- 输入：任务对象、异常对象。
- 输出：`None`
- 异常：写入失败时抛 `StorageError`
- 调用时机：异常收口阶段

### 7.9 主流程编排

#### `run_once(settings: AppSettings) -> list[FinalRecord]`

- 模块路径：`src/workflow/runner.py`
- 作用：执行一轮完整处理。
- 输入：`settings`
- 输出：`list[FinalRecord]`
- 异常：仅启动级错误向外抛，单文件错误内部消化
- 调用时机：`main.py` 入口
- 处理规则：
  - 扫描输入目录
  - 逐个处理文件
  - 单文件失败不影响其他文件
  - 返回全部成功和失败记录

#### `process_document(job: FileJob, settings: AppSettings, doc_type_rules: list[DocTypeRule], archive_rules: list[ArchiveRule]) -> FinalRecord`

- 模块路径：`src/workflow/runner.py`
- 作用：处理单个文件。
- 输入：任务、配置、规则。
- 输出：`FinalRecord`
- 异常：由调用方决定是否捕获，建议内部抛出后统一收口
- 调用时机：`run_once()` 内部
- 处理顺序：
  1. `parse_document`
  2. `analyze_document`
  3. `match_doc_type`
  4. `resolve_archive_folder`
  5. `resolve_suggested_name`
  6. `merge_ai_and_rules`
  7. `build_result_record`
  8. `save_result`
  9. `archive_original_file`
  10. `write_processing_log`

#### `handle_processing_error(job: FileJob, error: Exception) -> FinalRecord`

- 模块路径：`src/workflow/runner.py`
- 作用：将异常转成失败记录。
- 输入：任务对象、异常。
- 输出：失败状态的 `FinalRecord`
- 异常：无，内部应尽量容错
- 调用时机：单文件处理异常时
- 处理规则：
  - 记录错误日志。
  - 尽可能返回可展示的失败结果。

## 8. 核心规则设计

### 8.1 文档分类规则

- 命中“合同”“协议”优先判为“合同”。
- 命中“发票”“税额”优先判为“发票”。
- 未命中规则时为“待确认”。

### 8.2 归档目录规则

- 合同 -> `合同/待复核`
- 发票 -> `财务/发票`
- 未知类型 -> `待分类/待确认`

### 8.3 建议命名规则

- 优先使用 `AIResult.suggested_name`
- 否则使用原文件名
- 不允许生成空文件名

### 8.4 同名冲突规则

- 默认不覆盖
- 文件重名时在文件名后追加时间戳或序号

### 8.5 失败处理规则

- 单文件失败不影响整批任务
- 失败任务必须落日志
- 尽可能生成失败记录 `FinalRecord`

## 9. 输入输出与落盘约定

### 9.1 输入目录

- `data/inbox`

### 9.2 结果目录

- 目录：`data/results`
- 文件格式：JSON
- 命名：`<job_id>.json`

### 9.3 归档目录

- `data/archive/<target_folder>/`

### 9.4 日志目录

- `data/logs/app.log`

### 9.5 结果 JSON 示例

```json
{
  "job_id": "job_20260414_001",
  "source_file": "contract.txt",
  "status": "done",
  "doc_type": "合同",
  "summary": "这是一份关于项目合作的合同文本摘要。",
  "keywords": ["合同", "协议", "签署"],
  "suggested_folder": "合同/待复核",
  "suggested_name": "contract.txt",
  "confidence": 0.82,
  "result_file": "data/results/job_20260414_001.json",
  "archive_file": "data/archive/合同/待复核/contract.txt",
  "error_message": null
}
```

## 10. 边界情况与失败场景

### 10.1 空文本文件

- 触发条件：`.txt` 文件内容为空或清洗后为空。
- 预期行为：抛出 `ParseError`。
- 返回结果：失败 `FinalRecord`。
- 是否中断整体流程：否。

### 10.2 编码异常

- 触发条件：文件编码无法正确读取。
- 预期行为：抛出 `ParseError`。
- 返回结果：失败 `FinalRecord`。
- 是否中断整体流程：否。

### 10.3 无扩展名文件

- 触发条件：文件名无后缀。
- 预期行为：抛出 `UnsupportedFileError`。
- 返回结果：失败或跳过记录。
- 是否中断整体流程：否。

### 10.4 不支持格式

- 触发条件：输入 `.pdf`、`.docx` 等第一版未实现格式。
- 预期行为：抛出 `UnsupportedFileError`。
- 返回结果：失败或跳过记录。
- 是否中断整体流程：否。

### 10.5 Prompt 文件缺失

- 触发条件：`settings.prompt_file` 不存在或不可读。
- 预期行为：抛出 `AIError` 或启动阶段抛 `ConfigError`。
- 返回结果：启动失败或单文件失败。
- 是否中断整体流程：视发生阶段而定。

### 10.6 AI 输出字段缺失

- 触发条件：分析器返回不完整结构。
- 预期行为：抛出 `AIError` 或按兜底规则补齐。
- 返回结果：失败记录或待确认记录。
- 是否中断整体流程：否。

### 10.7 结果写入失败

- 触发条件：结果目录不可写。
- 预期行为：抛出 `StorageError`。
- 返回结果：失败 `FinalRecord`。
- 是否中断整体流程：否。

### 10.8 归档目录创建失败

- 触发条件：目标目录无法创建。
- 预期行为：抛出 `StorageError`。
- 返回结果：失败 `FinalRecord`。
- 是否中断整体流程：否。

### 10.9 原文件移动失败

- 触发条件：归档时移动文件失败。
- 预期行为：抛出 `StorageError`。
- 返回结果：失败 `FinalRecord`。
- 是否中断整体流程：否。

### 10.10 日志写入失败

- 触发条件：日志文件不可写。
- 预期行为：抛出 `StorageError`。
- 返回结果：失败记录或降级输出到控制台。
- 是否中断整体流程：不应影响其他文件处理。

## 11. 测试设计

### 11.1 功能测试

- 合同文本正常处理
- 发票文本正常处理
- 未知类型文本处理
- 不支持格式处理
- 空文本处理

### 11.2 异常测试

- 结果目录不可写
- Prompt 文件缺失
- 归档重名冲突
- 日志文件写入失败

### 11.3 验收标准

- 至少一个 `.txt` 文件完整跑通
- 生成结构化 JSON
- 原文件成功归档
- 单文件失败不导致整体崩溃
- 日志中可定位成功与失败原因

## 12. 开发顺序建议

1. `src/utils/models.py`
2. `src/utils/exceptions.py`
3. `src/workflow/config.py`
4. `src/watcher/scanner.py`
5. `src/parser/core.py`
6. `src/parser/txt_parser.py`
7. `src/ai/prompting.py`
8. `src/ai/analyzer.py`
9. `src/storage/rules.py`
10. `src/storage/results.py`
11. `src/storage/archive.py`
12. `src/storage/logging_service.py`
13. `src/workflow/runner.py`
14. `main.py`

## 13. 稳定接口与扩展约束

### 13.1 第一版需要稳定的公共内容

- 核心类型：
  - `AppSettings`
  - `FileJob`
  - `ParseResult`
  - `AIResult`
  - `FinalRecord`
- 主流程接口：
  - `run_once(settings) -> list[FinalRecord]`
  - `process_document(...) -> FinalRecord`
- 输出接口：
  - 结果 JSON 字段与命名
  - 日志文件位置与格式
- 异常接口：
  - 配置、解析、AI、存储的异常边界

### 13.2 后续扩展时保持不变的部分

- `ParseResult` 作为解析层统一输出，不因文件类型变化而改动主流程接口。
- `AIResult` 作为分析层统一输出，不因 Mock 或真实模型切换而改动下游模块。
- `FinalRecord` 作为落盘标准记录，新增字段时保持向后兼容。

## 14. 结论

第一版实现重点不是功能数量，而是闭环稳定性。  
只要系统能稳定完成 `.txt -> 解析 -> Mock AI -> 规则 -> 结果 -> 归档 -> 日志`，并且接口边界清晰、异常规则固定，就已经具备继续扩展到 Pro 版的基础。
