
import asyncio
from nanobot.config.loader import load_config
from nanobot.bus.queue import MessageBus
from nanobot.cli.commands import _make_provider
from nanobot.agent.loop import AgentLoop

async def main():
    print(">>> 正在加载配置...")
    # 1. 加载默认配置 (~/.nanobot/config.json)
    config = load_config()
    
    # [新增] 这里演示如何在代码中临时覆盖配置
    # 例如：临时修改模型 (如果不修改，则使用配置文件中的默认值)
    # config.agents.defaults.model = "openrouter/anthropic/claude-3-haiku"
    
    print(f">>> 当前使用模型: {config.agents.defaults.model}")
    print(f">>> 工作区路径: {config.workspace_path}")

    # 2. 初始化核心组件
    bus = MessageBus()
    
    # 创建 Provider (会自动根据 config 中的 API Key 初始化)
    provider = _make_provider(config)
    
    # 3. 创建 Agent 实例
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=0.7,           # 可以覆盖温度
        max_tokens=2048,           # 可以覆盖最大 Token 数
    )
    
    # 4. 直接发送消息并获取回复 (不经过 HTTP/WebSocket 网关)
    msg = "现在几点了？"
    print(f"\nUser: {msg}")
    
    # process_direct 是最简单的调用方式，适合脚本使用
    response = await agent.process_direct(msg)
    
    print(f"Agent: {response}")

if __name__ == "__main__":
    asyncio.run(main())
