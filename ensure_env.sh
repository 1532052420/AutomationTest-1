#!/usr/bin/env bash
# ============================================================
# 设备依赖检查（规矩：先查再装，缺才装，有就跳过，绝不动已有的）
# 用法: ./ensure_env.sh
# 依赖: adb (ANDROID_HOME/platform-tools)
# ============================================================
set -u
cd "$(dirname "$0")"

ADB="${ANDROID_HOME:-$HOME/Library/Android/sdk}/platform-tools/adb"
if [ ! -x "$ADB" ]; then
  echo "[错误] 找不到 adb: $ADB"; exit 1
fi

# 包名|apk路径|显示名（仅保留 Appium 自动化必需组件；墨迹天气演示应用已移除）
ENTRIES=(
  "io.appium.uiautomator2.server|node_modules/appium/node_modules/appium-uiautomator2-server/apks/appium-uiautomator2-server-v4.26.0.apk|uiautomator2 server"
  "io.appium.uiautomator2.server.test|node_modules/appium/node_modules/appium-uiautomator2-server/apks/appium-uiautomator2-server-debug-androidTest.apk|uiautomator2 test"
)

device="$("$ADB" devices | awk 'NR>1 && $2=="device" {print $1; exit}')"
if [ -z "$device" ]; then
  echo "[错误] 未检测到已授权的 Android 设备，请先连接手机并授权 USB 调试"; exit 1
fi
echo "[检查] 设备: $device"

installed="$("$ADB" shell pm list packages 2>/dev/null)"
need_install=0
for entry in "${ENTRIES[@]}"; do
  pkg="${entry%%|*}"
  rest="${entry#*|}"
  apk="${rest%%|*}"
  name="${rest#*|}"
  if echo "$installed" | grep -q "^package:$pkg\$"; then
    echo "[跳过] $name ($pkg) 已安装"
  else
    echo "[缺失] $name ($pkg) 未安装 → 开始安装 $apk"
    need_install=1
    python3 "$(pwd)/tools_install_apk.py" "$(pwd)/$apk"
    rc=$?
    if [ $rc -ne 0 ]; then
      echo "[失败] $pkg 安装未完成，请检查手机上的安装确认弹窗"; exit $rc
    fi
  fi
done

echo "=== instrumentation 注册检查 ==="
"$ADB" shell pm list instrumentation | grep -i uiautomator || echo "[提示] instrumentation 未注册（说明 server/test 未配对成功）"
[ $need_install -eq 0 ] && echo "[结论] 设备依赖齐全，无需安装"
