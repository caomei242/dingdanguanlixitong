# 草莓订单管理系统

## 开发启动

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install PySide6 requests Pillow pytest pytest-qt
python -m strawberry_order_management.app
```

## 测试

```bash
python3 -m pytest tests/test_address_extractor.py tests/test_config_store.py tests/test_history_store.py tests/test_order_parser.py tests/test_pipeline.py -q
python3 -m pytest tests/ui -q
```

## 打包方向

- 开发阶段：`python -m strawberry_order_management.app`
- 后续可选：`pyside6-deploy` 或 `pyinstaller`
