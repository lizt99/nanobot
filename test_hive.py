import os
import time
from nanobot.skills.agent_manager.tool import AgentManagerTool

# Ensure env vars are set (they should be in the container)
print("🔍 Checking Environment...")
print(f"API URL: {os.getenv('NANOBOT_AGENT_API_URL')}")
print(f"API KEY: {os.getenv('NANOBOT_AGENT_API_KEY')}")

tool = AgentManagerTool()

print("\n📋 Listing Agents (Expect empty or previous state)...")
print(tool.execute("list"))

print("\n🚀 Creating Test Agent 'hive-test-01'...")
# Note: Token is dummy, so it won't actually connect to Telegram, but container should start
try:
    print(tool.execute("create", 
        name="hive-test-01", 
        telegram_token="123456:ABC-DEF", 
        model="msp_gemini/gemini-3-pro-preview"
    ))
except Exception as e:
    print(f"❌ Creation Failed: {e}")

print("\n⏳ Waiting for provisioning...")
time.sleep(5)

print("\n📋 Listing Agents (Should see hive-test-01)...")
print(tool.execute("list"))

print("\nℹ️  Getting Info...")
info = tool.execute("info", name="hive-test-01")
print(info)

# Check for Nostr Pubkey
import ast
try:
    info_dict = ast.literal_eval(info)
    if 'runtime_config' in info_dict:
        cfg = info_dict['runtime_config']
        if 'nostr_public_key' in cfg:
            print(f"✅ Found Nostr Public Key: {cfg['nostr_public_key']}")
        else:
            print("⚠️ Nostr Public Key NOT found in runtime_config.")
except:
    pass

print("\n🛑 Stopping Agent...")
print(tool.execute("stop", name="hive-test-01"))

print("\n🗑️ Removing Agent...")
print(tool.execute("remove", name="hive-test-01"))

print("\n✅ Test Complete.")
