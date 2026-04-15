# 第一版接口文档：最小可运行主流程

## 文档目的

- 为项目第一版开发提供统一接口约定
- 限定第一版范围，避免一开始做成“大而全”
- 支持先完成单次处理闭环，再逐步扩展 watcher、PDF、DOCX 和真实模型调用

## 第一版目标

第一版只要求系统能够完成一次手动处理流程：

1. 从 `data/inbox` 扫描待处理文件
2. 只处理 `.txt` 文件
3. 解析文本内容并生成统一解析结果
4. 调用“可替换的 AI 分析接口”
5. 按规则生成文档类型和建议归档目录
6. 将结果保存到 `data/results`
7. 将原文件归档到 `data/archive`
8. 将处理日志写入 `data/logs`

验收标准：

- 能对至少一个 `.txt` 样本完成完整处理
- 能产出结构化 JSON 结果
- 能将原文件移动到归档目录
- 出错时能记录失败原因，不因单文件失败导致整体崩溃

## 第一版范围

### 本版包含

- 配置加载
- 目录初始化检查
- 手动单次执行 `run_once`
- `data/inbox` 目录扫描
- `.txt` 文本解析
- Mock AI 分析或规则驱动的占位分析
- 规则匹配
- 结果落盘
- 原文件归档
- 基础日志

### 本版不包含

- 目录监听循环 `run_watcher_loop`
- `.pdf` / `.docx` 解析
- 真实在线模型调用
- 数据库
- Web 界面
- 并发处理

## 建议目录与模块落位

第一版建议只实现以下模块：

- `src/workflow/config.py`
- `src/workflow/runner.py`
- `src/watcher/scanner.py`
- `src/parser/core.py`
- `src/parser/txt_parser.py`
- `src/ai/analyzer.py`
- `src/ai/prompting.py`
- `src/storage/rules.py`
- `src/storage/results.py`
- `src/storage/archive.py`
- `src/storage/logging_service.py`
- `src/utils/models.py`
- `src/utils/exceptions.py`

## 主流程

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
            -> build_result_record()
            -> save_result()
            -> archive_original_file()
            -> write_processing_log()
```

## 公共数据结构

以下类型建议放在 `src/utils/models.py`。

### `AppSettings`

用于保存运行配置。

建议字段：

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

### `FileJob`

表示待处理文件任务。

```python
@dataclass(slots=True)
class FileJob:
    job_id: str
    file_path: Path
    file_name: str
    extension: str
    status: str = "pending"
```

### `ParseResult`

表示解析模块产出。

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

### `AIResult`

表示 AI 或 Mock AI 的标准输出。

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

### `FinalRecord`

表示最终落盘记录。

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

### `DocTypeRule`

```python
@dataclass(slots=True)
class DocTypeRule:
    name: str
    keywords: list[str]
```

### `ArchiveRule`

```python
@dataclass(slots=True)
class ArchiveRule:
    doc_type: str
    target_folder: str
```

## 异常类型

以下异常建议放在 `src/utils/exceptions.py`。

### `ConfigError`

- 配置文件缺失
- 配置字段非法
- 初始化目录失败

### `UnsupportedFileError`

- 文件格式不在支持列表中

### `ParseError`

- 文本读取失败
- 文本为空且不满足处理条件

### `AIError`

- Prompt 文件读取失败
- 模拟分析逻辑异常
- 后续接真实模型时的调用失败

### `StorageError`

- 结果文件保存失败
- 归档失败
- 日志写入失败

## 接口定义

### 1. 配置与初始化

#### `load_settings(config_path: Path | None = None, env_path: Path | None = None) -> AppSettings`

- 模块路径：`src/workflow/config.py`
- 作用：读取 YAML 和环境变量，生成运行配置对象
- 输入：
  - `config_path`：配置文件路径，可为空
  - `env_path`：环境变量文件路径，可为空
- 输出：`AppSettings`
- 失败/异常：配置缺失或字段不合法时抛出 `ConfigError`

#### `load_rules(rules_path: Path) -> tuple[list[DocTypeRule], list[ArchiveRule]]`

- 模块路径：`src/workflow/config.py`
- 作用：加载文档类型规则和归档规则
- 输入：`rules_path`
- 输出：`(doc_type_rules, archive_rules)`
- 失败/异常：JSON 非法或字段缺失时抛出 `ConfigError`

#### `bootstrap_app(settings: AppSettings) -> None`

- 模块路径：`src/workflow/runner.py`
- 作用：检查目录、Prompt 文件和基础运行条件
- 输入：`settings`
- 输出：`None`
- 失败/异常：目录不可用或 Prompt 缺失时抛出 `ConfigError`

### 2. 扫描与任务生成

#### `scan_inbox(watch_dir: Path, supported_extensions: set[str]) -> list[FileJob]`

- 模块路径：`src/watcher/scanner.py`
- 作用：扫描输入目录，返回待处理文件任务列表
- 输入：
  - `watch_dir`
  - `supported_extensions`
- 输出：`list[FileJob]`
- 规则：
  - 第一版只返回 `.txt` 文件
  - 非文件项直接跳过
  - 按文件名排序，保证处理顺序稳定
- 失败/异常：目录不可读时抛出 `ConfigError`

#### `filter_supported_files(file_paths: list[Path], supported_extensions: set[str]) -> list[Path]`

- 模块路径：`src/watcher/scanner.py`
- 作用：过滤支持的后缀名
- 输入：路径列表与支持后缀集合
- 输出：过滤后的路径列表
- 失败/异常：无

### 3. 文档解析

#### `detect_file_extension(file_path: Path) -> str`

- 模块路径：`src/parser/core.py`
- 作用：提取并规范化扩展名
- 输入：`file_path`
- 输出：如 `".txt"`
- 失败/异常：无扩展名时抛出 `UnsupportedFileError`

#### `parse_document(file_path: Path) -> ParseResult`

- 模块路径：`src/parser/core.py`
- 作用：根据扩展名分发到具体解析器
- 输入：`file_path`
- 输出：`ParseResult`
- 第一版规则：
  - 仅支持 `.txt`
  - 其他格式直接抛出 `UnsupportedFileError`

#### `parse_txt(file_path: Path) -> ParseResult`

- 模块路径：`src/parser/txt_parser.py`
- 作用：读取文本文件并构造标准解析结果
- 输入：`file_path`
- 输出：`ParseResult`
- 失败/异常：读取失败或编码异常时抛出 `ParseError`

#### `clean_extracted_text(text: str) -> str`

- 模块路径：`src/parser/core.py`
- 作用：清洗文本，去掉多余空白和连续空行
- 输入：原始文本
- 输出：清洗后的文本
- 失败/异常：无

#### `build_parse_result(file_path: Path, raw_text: str, metadata: dict[str, Any] | None = None) -> ParseResult`

- 模块路径：`src/parser/core.py`
- 作用：统一封装解析结果
- 输入：原文件路径、文本、元信息
- 输出：`ParseResult`
- 失败/异常：清洗后文本为空时抛出 `ParseError`

### 4. AI 分析

第一版不强依赖真实模型，接口保留，内部可先使用 Mock 实现。

#### `load_prompt_template(prompt_file: Path) -> str`

- 模块路径：`src/ai/prompting.py`
- 作用：读取 Prompt 模板文件
- 输入：`prompt_file`
- 输出：模板字符串
- 失败/异常：文件不可读时抛出 `AIError`

#### `build_ai_input(parse_result: ParseResult, prompt_template: str) -> str`

- 模块路径：`src/ai/prompting.py`
- 作用：拼接传入模型的文本
- 输入：`parse_result`、`prompt_template`
- 输出：最终提示词文本
- 失败/异常：无

#### `analyze_document(parse_result: ParseResult, settings: AppSettings) -> AIResult`

- 模块路径：`src/ai/analyzer.py`
- 作用：对解析结果做分类与摘要
- 输入：`parse_result`、`settings`
- 输出：`AIResult`
- 第一版建议实现：
  - 优先读取 Prompt 模板
  - 默认走本地 Mock 分析
  - 后续再替换成真实 `call_llm`

#### `mock_analyze_document(parse_result: ParseResult) -> AIResult`

- 模块路径：`src/ai/analyzer.py`
- 作用：第一版的占位实现，用关键词和截断文本生成结果
- 输入：`parse_result`
- 输出：`AIResult`
- 规则建议：
  - 如果文本包含“合同”“协议”，输出 `doc_type="合同"`
  - 如果文本包含“发票”“税额”，输出 `doc_type="发票"`
  - 否则输出 `doc_type="待确认"`
  - `summary` 可截取前 80 到 120 个字符
  - `keywords` 可由命中词和高频词构成简化版本

### 5. 规则与结果修正

#### `match_doc_type(text: str, ai_result: AIResult, rules: list[DocTypeRule]) -> str`

- 模块路径：`src/storage/rules.py`
- 作用：根据规则修正最终文档类型
- 输入：文本、AI 结果、规则列表
- 输出：最终 `doc_type`
- 失败/异常：无

#### `resolve_archive_folder(doc_type: str, rules: list[ArchiveRule]) -> str`

- 模块路径：`src/storage/rules.py`
- 作用：根据文档类型决定归档目录
- 输入：`doc_type`、归档规则
- 输出：目标目录字符串
- 兜底值：`"待分类/待确认"`

#### `resolve_suggested_name(ai_result: AIResult, source_path: Path) -> str`

- 模块路径：`src/storage/rules.py`
- 作用：生成建议文件名
- 输入：`ai_result`、源文件路径
- 输出：建议文件名
- 规则：
  - 优先使用 `ai_result.suggested_name`
  - 否则使用原始文件名

#### `merge_ai_and_rules(ai_result: AIResult, resolved_doc_type: str, resolved_folder: str, suggested_name: str) -> AIResult`

- 模块路径：`src/storage/rules.py`
- 作用：将规则结果覆盖回标准输出对象
- 输入：AI 结果和规则决策结果
- 输出：修正后的 `AIResult`

### 6. 结果落盘

#### `build_result_record(job: FileJob, parse_result: ParseResult, ai_result: AIResult, result_file: Path | None = None, archive_file: Path | None = None, status: str = "done", error_message: str | None = None) -> FinalRecord`

- 模块路径：`src/storage/results.py`
- 作用：构建最终结果对象
- 输入：任务、解析结果、AI 结果及可选落盘路径
- 输出：`FinalRecord`
- 失败/异常：无

#### `save_result(record: FinalRecord, result_dir: Path, overwrite: bool = False) -> Path`

- 模块路径：`src/storage/results.py`
- 作用：将结果写入 JSON 文件
- 输入：`record`、结果目录、是否允许覆盖
- 输出：结果文件路径
- 文件命名建议：`<job_id>.json`
- 失败/异常：写入失败时抛出 `StorageError`

#### `result_exists(result_path: Path) -> bool`

- 模块路径：`src/storage/results.py`
- 作用：判断结果文件是否已存在
- 输入：结果路径
- 输出：`bool`

### 7. 归档处理

#### `ensure_archive_path(archive_root: Path, target_folder: str) -> Path`

- 模块路径：`src/storage/archive.py`
- 作用：确保归档目录存在
- 输入：归档根目录、目标子目录
- 输出：归档目录路径
- 失败/异常：目录不可创建时抛出 `StorageError`

#### `handle_name_conflict(target_path: Path) -> Path`

- 模块路径：`src/storage/archive.py`
- 作用：处理重名文件
- 输入：目标路径
- 输出：可安全写入的新路径
- 第一版建议：文件名后追加时间戳

#### `archive_original_file(file_path: Path, archive_root: Path, target_folder: str) -> Path`

- 模块路径：`src/storage/archive.py`
- 作用：归档原始输入文件
- 输入：原文件、归档根目录、目标子目录
- 输出：最终归档文件路径
- 失败/异常：移动失败时抛出 `StorageError`

### 8. 日志

#### `write_processing_log(level: str, message: str, context: dict[str, Any] | None = None) -> None`

- 模块路径：`src/storage/logging_service.py`
- 作用：写入处理日志
- 输入：级别、消息、上下文
- 输出：`None`
- 第一版要求：
  - 至少能写入本地文本日志
  - 上下文中避免写入敏感全文

#### `write_error_log(job: FileJob, error: Exception) -> None`

- 模块路径：`src/storage/logging_service.py`
- 作用：记录失败任务和错误信息
- 输入：任务对象、异常对象
- 输出：`None`

### 9. 主流程编排

#### `run_once(settings: AppSettings) -> list[FinalRecord]`

- 模块路径：`src/workflow/runner.py`
- 作用：执行一轮完整处理
- 输入：`settings`
- 输出：`list[FinalRecord]`
- 行为要求：
  - 扫描输入目录
  - 逐个处理文件
  - 单文件失败不影响其他文件
  - 返回全部成功和失败记录

#### `process_document(job: FileJob, settings: AppSettings, doc_type_rules: list[DocTypeRule], archive_rules: list[ArchiveRule]) -> FinalRecord`

- 模块路径：`src/workflow/runner.py`
- 作用：处理单个文件
- 输入：任务、配置、规则
- 输出：`FinalRecord`
- 内部顺序：
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
- 作用：将异常转成失败记录
- 输入：任务对象、异常
- 输出：失败状态的 `FinalRecord`
- 行为要求：
  - 记录错误日志
  - 尽可能返回可落盘或可展示的失败结果

## `main.py` 第一版入口约定

建议 `main.py` 只做以下事情：

1. 调用 `load_settings`
2. 调用 `load_rules`
3. 调用 `bootstrap_app`
4. 调用 `run_once`
5. 打印简短处理结果摘要

`main.py` 不应堆积解析、规则、落盘细节。

## 输出文件约定

### 结果文件

- 目录：`data/results`
- 格式：JSON
- 命名建议：`<job_id>.json`

示例：

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

### 日志文件

- 目录：`data/logs`
- 文件：`app.log`

## 第一版开发顺序

推荐按下面顺序实现，不要反过来：

1. `src/utils/models.py`
2. `src/utils/exceptions.py`
3. `src/workflow/config.py`
4. `src/watcher/scanner.py`
5. `src/parser/core.py` 与 `src/parser/txt_parser.py`
6. `src/ai/prompting.py`
7. `src/ai/analyzer.py` 的 Mock 版本
8. `src/storage/rules.py`
9. `src/storage/results.py`
10. `src/storage/archive.py`
11. `src/storage/logging_service.py`
12. `src/workflow/runner.py`
13. `main.py`

## 第一版验收用例

至少覆盖以下场景：

### 用例 1：正常处理合同文本

- 输入：包含“合同”“协议”等关键词的 `.txt`
- 预期：
  - 成功生成结果 JSON
  - 正确归档到 `合同/待复核`
  - 日志中有成功记录

### 用例 2：正常处理发票文本

- 输入：包含“发票”“税额”等关键词的 `.txt`
- 预期：
  - `doc_type` 为“发票”
  - 归档目录为 `财务/发票`

### 用例 3：未知类型文本

- 输入：无明显关键词的 `.txt`
- 预期：
  - `doc_type` 为“待确认”
  - 归档目录为 `待分类/待确认`

### 用例 4：不支持文件格式

- 输入：`.pdf` 或其他未实现格式
- 预期：
  - 生成失败记录或跳过记录
  - 日志中有明确原因

### 用例 5：空文本文件

- 输入：空的 `.txt`
- 预期：
  - 抛出 `ParseError`
  - 记录失败结果

## 后续升级方向

第一版完成后，再按这个顺序升级：

1. 增加 `pdf/docx` 解析
2. 接入真实 LLM 调用
3. 增加 `run_watcher_loop`
4. 完善状态管理
5. 增加自动化测试
6. 增加结果查询能力

## 结论

第一版的重点不是“功能多”，而是“闭环稳定”。  
只要这版能稳定完成 `.txt -> 解析 -> Mock AI -> 规则 -> 结果 -> 归档 -> 日志`，就已经具备后续扩展基础。
