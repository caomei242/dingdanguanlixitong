# 草莓订单管理系统

## 开发启动

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install PySide6 requests Pillow playwright pytest pytest-qt
python3 -m playwright install chromium
python -m strawberry_order_management.app
```

## 桌面外观说明

- macOS 桌面应用默认固定为浅色模式，不跟随系统深色模式自动切换。
- 如果后续新增页面或控件时出现黑色横条、黑色竖条、黑色 tooltip 或图表漏底，优先检查应用启动 palette、`QTabWidget::pane`、`QAbstractScrollArea::viewport`、`QSplitter::handle` 和图表容器背景是否显式设置为浅色。

## 测试

```bash
python3 -m pytest tests/test_address_extractor.py tests/test_config_store.py tests/test_history_store.py tests/test_order_parser.py tests/test_pipeline.py -q
python3 -m pytest tests/ui -q
```

## 订单识别与 OCR

系统支持两条截图识别链路：

- 普通 MiniMax OCR：走接口配置里的 API Host / API Key。
- MiniMax MCP OCR：设置页勾选“启用 MiniMax MCP OCR”后，走 `minimax-coding-plan-mcp` 的 `understand_image` 工具。

MCP OCR 当前按“一行一个 JSON”的 stdio 协议调用，同时兼容 `Content-Length` 响应。为避免界面长时间停在“剪贴板截图：OCR识别中...”，单次 MCP 响应有 90 秒超时；超时后会给中文提示，可直接重试。

截图解析会尽量兜底：

- 多订单列表截图优先走批量识别，录单页可在多单之间切换。
- 如果 OCR 漏掉顶部 `订单编号 / 订单号`，但识别到了抖店商品区的 `商品单ID`，系统会把 `商品单ID` 当作订单号兜底生成可编辑订单。
- 字段不完整时先生成可编辑草稿，不直接写飞书，方便人工补齐。

## 店铺默认与飞书字段

当前录单默认值不再只有一个“默认店铺”，而是按平台分开保存：

- `录单默认平台`
- `抖店默认店铺`
- `微信默认店铺`

没显式传 `shop_name / platform` 时，系统会先取 `录单默认平台`，再带出该平台对应的默认店铺。

飞书写入和历史页 `保存修改并重新写入飞书` 现在也会先读取当前飞书表真实字段：

- 本地映射里有、但飞书表里已不存在的字段，会自动跳过，不再整单报错。
- 成功后会在状态里提示 `已跳过缺失字段：...`。
- 如果想把这些旧映射彻底清掉，可以到 `设置 -> 店铺映射` 点 `永久清空缺失字段映射`，再 `保存/应用`。

## 历史工作台排序

历史工作台左侧订单列表默认按 `下单时间` 倒序排列：

- 最新下单的订单排在最上面，方便优先处理最新订单。
- 排序主键优先使用 `order_snapshot.placed_at`。
- 如果个别旧记录缺少下单时间，会退回 `created_at` 和 `record_id` 做稳定排序，不影响其他订单正常靠前显示。

## 手机助手录单

草莓系统内置本地手机录单 HTTP 入口，适合给爱马仕、OpenClaw 或私有隧道调用。默认端口是 `9020`，入口页面是：

```text
http://127.0.0.1:9020/mobile
```

核心接口：

- `POST /mobile/orders/preview`
- `POST /mobile/orders/drafts`
- `POST /mobile/orders/preview-batch`
- `POST /mobile/orders/drafts-batch`

所有接口都需要：

```text
Authorization: Bearer <API_KEY>
```

第一版手机入口只创建 `待确认` 草稿，不直接写飞书、不自动拍单。详细接入方式见 `docs/mobile-helper/hermes-integration.md`。

## 本地自动拍单联调

先启动一个本地模拟拍单服务：

```bash
python3 -m strawberry_order_management.mock_auto_order_service --host 127.0.0.1 --port 9000 --api-key bridge-key
```

然后在草莓系统的“设置 -> 接口配置 -> 自动拍单服务”里填：

```text
启用 HTTP 桥接: 开
Base URL: http://127.0.0.1:9000
API Key: bridge-key
创建任务路径: /auto-order/tasks
查询任务路径模板: /auto-order/tasks/{task_id}
轮询间隔秒数: 3
超时秒数: 1200
```

这个模拟服务会串行处理任务：
- 正常采购位会返回 `待付款` 和假的 `JD` 单号
- 缺少 `jd_link` 的采购位会返回失败
- 商品名里带 `fail / 失败 / error` 的采购位会被模拟成失败

## 真实自动拍单服务

先确保：
- 已安装 `playwright`，并执行过 `python3 -m playwright install chromium`
- 每个京东账号环境都已经手动登录
- 每个京东账号里都预先准备了 1 个自定义标签为 `自动拍单` 的专用地址

启动真实自动拍单服务：

```bash
python3 -m strawberry_order_management.mock_auto_order_service --help
strawberry-real-auto-order --host 127.0.0.1 --port 9000 --api-key bridge-key
strawberry-real-auto-order --host 127.0.0.1 --port 9000 --api-key bridge-key --stop-before-submit
```

说明：
- 第一版只支持“商品页直接立即购买”
- 地址处理固定为：`结果一` 走京东地址粘贴识别，`结果二` 追加到门牌号末尾
- `结果一` 缺失时，草莓系统会直接本地失败，不会发起真实拍单请求
- 浏览器默认可见运行，方便你观察真实操作过程
- 首次真实联调建议先带 `--stop-before-submit`，流程会停在提交前检查点，不会真正提交订单

## 打包方向

- 开发阶段：`python -m strawberry_order_management.app`
- 后续可选：`pyside6-deploy` 或 `pyinstaller`
