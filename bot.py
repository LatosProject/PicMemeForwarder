import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotAdapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotAdapter)

from nonebot import require

require("nonebot_plugin_apscheduler")

nonebot.load_plugins("src/plugins")

if __name__ == "__main__":
    nonebot.run()
