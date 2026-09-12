#!/usr/bin/env bash
# ============================================================
# 自动化测试平台 · 双击启动器（macOS）
# ============================================================
# 说明（重要）：
#   · 本启动器启动的是【后台服务】——关掉本窗口或浏览器网页，服务仍在运行
#   · 浏览器网页只是【操作界面】，随时可关，不影响测试执行
#   · 停止服务请用本启动器菜单 3/4，或终端执行 ./run.sh stop-platform
# ============================================================
cd "$(dirname "$0")" || exit 1

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

plat_up()   { curl -s --max-time 2 http://127.0.0.1:8080/api/status >/dev/null 2>&1; }
loc_up()    { curl -s --max-time 2 http://127.0.0.1:8001/api/status >/dev/null 2>&1; }
appium_up() { curl -s --max-time 2 http://127.0.0.1:4726/wd/hub/status >/dev/null 2>&1; }

start_platform() {
  if plat_up; then
    echo -e "${GREEN}平台服务已在运行（无需重复启动）${NC}"
  else
    echo "正在启动平台服务（后台）…"
    mkdir -p logs
    nohup .venv/bin/python web_platform/app.py > logs/platform.log 2>&1 &
    for i in $(seq 1 20); do plat_up && break; sleep 0.5; done
    plat_up && echo -e "${GREEN}✓ 平台服务已启动（端口 8080，日志 logs/platform.log）${NC}" \
             || echo -e "${RED}✗ 平台服务启动失败，请查看 logs/platform.log${NC}"
  fi
  echo "正在打开操作网页…"
  open http://127.0.0.1:8080/
  echo -e "${YELLOW}提示：网页只是界面，关闭网页不影响服务运行${NC}"
}

start_locator() {
  if loc_up; then
    echo -e "${GREEN}元素定位器已在运行${NC}"
  else
    echo "正在启动元素定位器服务（后台）…"
    mkdir -p logs
    nohup .venv/bin/python element_locator/server.py > logs/element_locator.log 2>&1 &
    for i in $(seq 1 20); do loc_up && break; sleep 0.5; done
    loc_up && echo -e "${GREEN}✓ 元素定位器已启动（端口 8001）${NC}" \
             || echo -e "${RED}✗ 启动失败，请查看 logs/element_locator.log${NC}"
  fi
  open http://127.0.0.1:8001/
}

status_all() {
  plat_up   && echo -e "平台服务(8080)   ${GREEN}● 运行中${NC}   网页: http://127.0.0.1:8080/" \
            || echo -e "平台服务(8080)   ${RED}○ 已停止${NC}"
  loc_up    && echo -e "元素定位器(8001) ${GREEN}● 运行中${NC}   网页: http://127.0.0.1:8001/" \
            || echo -e "元素定位器(8001) ${RED}○ 已停止${NC}"
  appium_up && echo -e "Appium(4726)     ${GREEN}● 运行中${NC}" \
            || echo -e "Appium(4726)     ${RED}○ 已停止${NC}"
  local n
  n=$("$HOME/Library/Android/sdk/platform-tools/adb" devices 2>/dev/null | grep -c "device$") || n=0
  if [ "${n:-0}" -gt 0 ]; then
    echo -e "Android 设备      ${GREEN}● 在线 ×${n}${NC}"
  else
    echo -e "Android 设备      ${RED}○ 无在线设备${NC}"
  fi
}

while true; do
  echo ""
  echo "================ 自动化测试平台 ================"
  echo " 1) 启动平台服务并打开网页"
  echo " 2) 启动元素定位器"
  echo " 3) 停止平台服务"
  echo " 4) 停止元素定位器"
  echo " 5) 查看全部服务状态"
  echo " q) 退出启动器（不停止已启动的服务）"
  echo "================================================"
  read -rp "请选择: " choice
  case "$choice" in
    1) start_platform ;;
    2) start_locator ;;
    3) pkill -f "web_platform/app.py" 2>/dev/null \
         && echo -e "${GREEN}✓ 平台服务已停止${NC}" || echo "平台服务未在运行" ;;
    4) pkill -f "element_locator/server.py" 2>/dev/null \
         && echo -e "${GREEN}✓ 元素定位器已停止${NC}" || echo "元素定位器未在运行" ;;
    5) status_all ;;
    q|Q) echo "已退出（运行中的服务不受影响）"; exit 0 ;;
    *) echo "无效选择" ;;
  esac
done
