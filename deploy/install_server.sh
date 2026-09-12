#!/usr/bin/env bash
# ============================================================
# AutomationTest 服务器一键初始化（Ubuntu 20.04+/Debian，需 root 或 sudo）
# 用法: sudo bash deploy/install_server.sh [--with-appium]
#   --with-appium  额外安装 Node + Appium 3 + uiautomator2 驱动
#                  （仅当服务器要接 USB 真机跑 APP 用例时才需要）
# ============================================================
set -e
cd "$(dirname "$0")/.."
WITH_APPIUM=${1:-}

echo "==> 1/6 系统依赖"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git curl unzip \
  openjdk-8-jdk android-tools-adb

echo "==> 2/6 代码目录 /opt/AutomationTest"
if [ ! -d /opt/AutomationTest ]; then
  git clone https://github.com/1532052420/AutomationTest-1.git /opt/AutomationTest
fi
cd /opt/AutomationTest
git pull || true

echo "==> 3/6 Python 虚拟环境与依赖"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> 4/6 allure 命令行（测试报告）"
if ! command -v allure >/dev/null 2>&1; then
  curl -sL https://github.com/allure-framework/allure2/releases/latest/download/allure-2.30.0.tgz -o /tmp/allure.tgz
  tar -xzf /tmp/allure.tgz -C /opt
  ln -sf /opt/allure-2.30.0/bin/allure /usr/local/bin/allure
fi

echo "==> 5/6 systemd 服务（开机自启 + 崩溃自动拉起）"
cp deploy/systemd/automation-platform.service /etc/systemd/system/
cp deploy/systemd/element-locator.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now automation-platform
systemctl enable --now element-locator

echo "==> 6/6 Appium（可选）"
if [ "$WITH_APPIUM" = "--with-appium" ]; then
  apt-get install -y nodejs npm
  npm install -g appium@3
  appium driver install uiautomator2
  echo "提示：还需 USB 连接真机并执行 adb devices 授权；APP 用例只能在接真机的机器上跑"
fi

echo ""
echo "✅ 初始化完成。服务状态: systemctl status automation-platform element-locator"
echo "   下一步: 配置 nginx 反代（参考 deploy/nginx-automation.conf）并提供给团队访问"
