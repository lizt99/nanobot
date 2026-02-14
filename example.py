
import asyncio
import os
from pathlib import Path
from nanobot.config.loader import load_config, save_config
from nanobot.config.schema import Config
from nanobot.bus.queue import MessageBus
from nanobot.cli.commands import _make_provider
from nanobot.agent.loop import AgentLoop

# --- 配置部分 ---
CUSTOM_ROOT = Path("/Users/Doc/code/temp/nanobot-workspace/workspace-gary")

def ensure_initialized():
    """确保自定义目录和配置已初始化"""
    print(f">>> 检查环境: {CUSTOM_ROOT}")
    CUSTOM_ROOT.mkdir(parents=True, exist_ok=True)
    
    # 设置环境变量，强制 nanobot 在此目录下查找 config.json
    os.environ["NANOBOT_CONFIG_DIR"] = str(CUSTOM_ROOT)
    
    config_path = CUSTOM_ROOT / "config.json"
    workspace_path = CUSTOM_ROOT / "workspace"
    
    # 1. 如果配置不存在，创建并预填充
    if not config_path.exists():
        print(f">>> 初始化配置: {config_path}")
        config = Config()
        
        # 设置工作区路径
        config.agents.defaults.workspace = str(workspace_path)
        
        # 预填充 API 配置 (基于您之前的设置)
        config.agents.defaults.model = "openai/gemini-3-flash-preview"
        config.providers.openai.api_key = "sk-7v1x212WwboXuKkemc1Prw"
        config.providers.openai.api_base = "https://aigateway-sandbox.mspbots.ai/v1"
        
        save_config(config)
    
    # 2. 如果工作区文件不存在，创建基础模板
    if not workspace_path.exists():
        print(f">>> 初始化工作区: {workspace_path}")
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        (workspace_path / "AGENTS.md").write_text("# Identity\nYou are Gary.")
        (workspace_path / "SOUL.md").write_text("# Soul\nI am Gary, a helpful assistant.")
        
        # 创建记忆目录
        (workspace_path / "memory").mkdir(exist_ok=True)
        (workspace_path / "memory" / "MEMORY.md").write_text("# Memory\n")
        (workspace_path / "memory" / "HISTORY.md").write_text("")

    return load_config()

async def main():
    # 1. 环境初始化
    config = ensure_initialized()
    print(f">>> 当前配置路径: {os.environ.get('NANOBOT_CONFIG_DIR')}")
    print(f">>> 当前工作区: {config.workspace_path}")
    
    # 2. 初始化核心组件
    bus = MessageBus()
    provider = _make_provider(config)
    
    # 3. 创建 Agent
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
    )
    
    # 4. 发送测试消息
    msg = "安装weather skill"
    print(f"\nUser: {msg}")
    
    response = await agent.process_direct(msg)
    print(f"Agent: {response}")

if __name__ == "__main__":
    asyncio.run(main())
