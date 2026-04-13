#!/bin/bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

if [ -z "${PYTHON_BIN:-}" ]; then
  echo "未找到可用的 Python 3。"
  read -r -p "按回车关闭..."
  exit 1
fi

export PYTHONPATH="$PROJECT_DIR/src"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-cocoa}"

echo "正在启动 草莓订单管理系统..."
echo "项目目录: $PROJECT_DIR"

if ! "$PYTHON_BIN" -m strawberry_order_management.app; then
  echo
  echo "启动失败，请把这里的报错截图发给我。"
  read -r -p "按回车关闭..."
  exit 1
fi
