from dataclasses import dataclass
from pathlib import Path
import json

from src.utils.exceptions import (
    AIError,
    ConfigError,
    ParseError,
    StorageError,
    UnsupportedFileError,
)
from src.utils.models import AIResult, FileJob, FinalRecord, ParseResult


VALID_RECORD_STATUSES = {"done", "failed", "skipped"}
FAILED_DOC_TYPE = "处理失败"
SKIPPED_DOC_TYPE = "已跳过"


@dataclass(slots=True)
class ResultBuildContext:
    """
    任务收口时使用的上下文。

    主流程后续可以在每个阶段更新这个对象，异常时直接交给
    build_result_record_from_context() 自动生成 FinalRecord。
    """

    job: FileJob
    stage: str = "pending"
    parse_result: ParseResult | None = None
    ai_result: AIResult | None = None
    result_file: Path | None = None
    archive_file: Path | None = None


def resolve_record_status(
    error: Exception | None = None,
    status: str | None = None,
) -> str:
    """
    根据显式状态或异常类型推导 FinalRecord.status。

    规则：
        - 显式传入 status 时优先使用，但必须是合法值。
        - UnsupportedFileError -> skipped
        - 其他已知异常和未知异常 -> failed
        - 没有异常且未显式指定 -> done
    """
    if status is not None:
        if status not in VALID_RECORD_STATUSES:
            raise ValueError(f"不支持的状态: {status}")
        return status

    if error is None:
        return "done"

    if isinstance(error, UnsupportedFileError):
        return "skipped"

    if isinstance(error, (ParseError, AIError, StorageError, ConfigError)):
        return "failed"

    return "failed"


def resolve_error_message(
    error: Exception | None = None,
    error_message: str | None = None,
    stage: str | None = None,
) -> str | None:
    """
    统一收口错误信息。

    显式 error_message 优先，其次退回异常字符串；如提供 stage，则追加阶段前缀。
    """
    resolved: str | None
    if error_message is not None:
        normalized = error_message.strip()
        resolved = normalized or None
    elif error is not None:
        resolved = str(error).strip() or error.__class__.__name__
    else:
        resolved = None

    if resolved is None or not stage:
        return resolved

    if resolved.startswith("[") and "]" in resolved:
        return resolved

    return f"[{stage}] {resolved}"


def _normalize_output_path(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path) if path.exists() else None


def _default_doc_type(status: str) -> str:
    if status == "failed":
        return FAILED_DOC_TYPE
    if status == "skipped":
        return SKIPPED_DOC_TYPE
    return "待确认"


def build_result_record(
    job: FileJob,
    parse_result: ParseResult | None = None,
    ai_result: AIResult | None = None,
    result_file: Path | None = None,
    archive_file: Path | None = None,
    status: str | None = None,
    error_message: str | None = None,
    error: Exception | None = None,
    stage: str | None = None,
) -> FinalRecord:
    """
    构建最终结果对象。

    处理规则：
        路径字段在落盘前允许为空。
        失败记录必须带 error_message。
        跳过记录建议保留错误或跳过原因，便于追踪。
    """
    resolved_status = resolve_record_status(error=error, status=status)
    resolved_error_message = resolve_error_message(
        error=error,
        error_message=error_message,
        stage=stage,
    )

    if resolved_status == "failed" and resolved_error_message is None:
        raise StorageError("失败记录必须提供 error_message 或 error。")

    source_file = parse_result.file_name if parse_result is not None else job.file_name
    doc_type = ai_result.doc_type if ai_result is not None else _default_doc_type(resolved_status)

    if ai_result is not None:
        suggested_name = ai_result.suggested_name
    elif parse_result is not None:
        suggested_name = Path(parse_result.file_path).name
    else:
        suggested_name = job.file_name

    return FinalRecord(
        job_id=job.job_id,
        source_file=source_file,
        status=resolved_status,
        doc_type=doc_type,
        summary=ai_result.summary if ai_result is not None else "",
        keywords=ai_result.keywords if ai_result is not None else [],
        suggested_folder=ai_result.suggested_folder if ai_result is not None else "",
        suggested_name=suggested_name,
        confidence=ai_result.confidence if ai_result is not None else 0.0,
        result_file=_normalize_output_path(result_file),
        archive_file=_normalize_output_path(archive_file),
        error_message=resolved_error_message,
    )


def build_result_record_from_context(
    context: ResultBuildContext,
    error: Exception | None = None,
    status: str | None = None,
    error_message: str | None = None,
) -> FinalRecord:
    """
    基于任务上下文自动构建 FinalRecord。

    用法：
        - 成功时：主流程把 parse_result / ai_result / 路径写回 context 后调用。
        - 失败时：在最外层 except 中传入 error，自动推导 status 并写入错误信息。
    """
    return build_result_record(
        job=context.job,
        parse_result=context.parse_result,
        ai_result=context.ai_result,
        result_file=context.result_file,
        archive_file=context.archive_file,
        status=status,
        error_message=error_message,
        error=error,
        stage=context.stage,
    )

def save_result(record: FinalRecord, result_dir: Path, overwrite: bool = False) -> Path:
    """
    将结果写入JSON文件
    """
    result_path = result_dir / f"{record.job_id}.json" 
     
    if result_exists(result_path) and not overwrite:
        raise StorageError(f"文件已存在且不允许覆写{str(result_path)}")

    try:
        with result_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, indent=2))
    except OSError as e:
        raise StorageError("写入JSON文件失败") from e
    
    return result_path
    
def result_exists(result_path: Path) -> bool:
    return result_path.exists() and result_path.is_file()
