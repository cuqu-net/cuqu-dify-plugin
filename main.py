import sys

from dify_plugin import DifyPluginEnv, Plugin

# CUQU 只读插件：单次上游请求约 100 条活动，60s 足够留余量。
plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=120))

if __name__ == "__main__":
    try:
        plugin.run()
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"cuqu plugin fatal: {exc}\n")
        raise
