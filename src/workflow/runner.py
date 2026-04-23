from src.utils.models import AppSettings
from src.utils.exceptions import ConfigError

def bootstrap_app(settings: AppSettings) -> None:
    """
        检查目录、Prompt 文件和基础运行条件。

        需要的目录不存在时自动创建。prompt_file 不存在时直接报错。
  
        Args:
            settings (AppSettings): 应用设置对象，包含所有必要的配置参数。

        Returns:
            None  
    """
    try:
        # 检查并创建必要的目录
        for dir_attr in ['result_directory', 'archive_directory', 'temp_directory', 'log_directory']:
            dir_path = getattr(settings, dir_attr)
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)

            if not dir_path.is_dir():
                raise ConfigError(f"路径不是目录: {dir_path}")
        # 检查监视目录是否存在
        if not settings.watch_directory.exists():
            raise ConfigError(f"监视目录不存在: {settings.watch_directory}") 
        if not settings.watch_directory.is_dir():
            raise ConfigError(f"监视路径不是目录: {settings.watch_directory}")       
        # 检查 Prompt 文件是否存在
        if not settings.prompt_file.exists():
            raise ConfigError(f"Prompt文件缺失: {settings.prompt_file}")
        if not settings.prompt_file.is_file():
            raise ConfigError(f"Prompt路径不是文件: {settings.prompt_file}")
    except OSError as e:
        raise ConfigError(f"应用启动失败: {e}")    
        


