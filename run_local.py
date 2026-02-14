#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def main():
    """
    运行此脚本以使用当前目录作为配置和工作区启动 nanobot。
    它会自动设置 NANOBOT_CONFIG_DIR 环境变量。
    """
    # 1. 设置配置目录为当前脚本所在目录
    current_dir = Path(__file__).parent.resolve()
    os.environ["NANOBOT_CONFIG_DIR"] = str(current_dir)
    
    print(f">>> [Local Runner] Running nanobot with config in: {current_dir}")
    
    # 2. 检查是否存在 config.json，如果没有则提示用户初始化
    config_path = current_dir / "config.json"
    if not config_path.exists():
        if "onboard" not in sys.argv:
            print(">>> [Local Runner] Config not found in current directory.")
            print(">>> [Local Runner] Running 'onboard' to initialize...")
            sys.argv = [sys.argv[0], "onboard"]
    
    # 3. 导入并运行 nanobot CLI
    try:
        from nanobot.cli.commands import app
        app()
    except ImportError:
        # 如果未安装包，尝试将当前目录添加到 sys.path
        sys.path.insert(0, str(current_dir))
        try:
            from nanobot.cli.commands import app
            app()
        except ImportError as e:
            print(f"Error: Could not import nanobot. Make sure dependencies are installed.\n{e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
