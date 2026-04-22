import os
from datetime import datetime
from pathlib import Path

from src.utils.exceptions import ConfigError
from src.utils.models import FileJob


def filter_supported_files(file_paths: list[Path], supported_extensions: set[str]) -> list[Path]:
    """
    过滤出支持的文件类型。
    非文件项直接剔除。扩展名比较按小写处理。

    Args:
        file_paths: 待过滤的文件路径列表。
        supported_extensions: 支持的文件后缀集合。
    Returns:
        过滤后的文件路径列表。
    """
    normalized_extensions = {extension.lower() for extension in supported_extensions}

    return [
        file_path
        for file_path in file_paths
        if file_path.is_file() and file_path.suffix.lower() in normalized_extensions
    ]


def scan_inbox(watch_dir: Path, supported_extensions: set[str]) -> list[FileJob]:
    """扫描输入目录并生成待处理任务列表。

    仅处理普通文件。后缀统一转小写。按文件名排序。
    Args:
        watch_dir: 待扫描目录。
        supported_extensions: 支持的文件后缀集合。
    
    Returns:
        待处理任务列表，每个任务包含文件路径和文件名。
    """
    file_jobs = []

    if not watch_dir.exists():
        raise ConfigError(f"Watch directory does not exist: {watch_dir}")

    try:
        watch_files = sorted(os.listdir(watch_dir))
    except OSError as exc:
        raise ConfigError(f"Failed to scan watch directory: {watch_dir}") from exc

    valid_files = filter_supported_files(
        [watch_dir / file_name for file_name in watch_files],
        supported_extensions,
    )
    batch_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    for index, file_path in enumerate(valid_files):
        file_jobs.append(
            FileJob(
                job_id=f"{batch_time}_{index:04d}",
                file_path=file_path,
                file_name=file_path.name,
                extension=file_path.suffix.lower(),
            )
        )

    return file_jobs
