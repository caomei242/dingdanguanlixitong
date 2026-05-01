# 草莓订单管理系统订单数据类型说明书

这份说明书基于当前代码里的真实类型与存储结构整理，主要对应：

- `src/strawberry_order_management/models.py`
- `src/strawberry_order_management/history.py`
- `src/strawberry_order_management/services/pipeline.py`
- `src/strawberry_order_management/services/auto_order.py`
- `src/strawberry_order_management/ui/pages/history_page.py`

## 一句话先讲清

这个系统不是只有一个“订单类型”。

它实际上把订单拆成了 5 层：

1. `ParsedOrder`
   OCR 和文本解析后的订单草稿。
2. `ProcurementItem`
   订单里的采购位明细，固定最多 3 个槽位。
3. `HistoryRow`
   真正落库到 `history.json` 的长期记录。
4. `OrderSnapshot / AddressSnapshot`
   历史记录里的业务快照，保证后续编辑、重算和回放都基于快照。
5. `AutoOrder*`
   自动拍单请求、任务、结果、调试状态。

这层拆分很重要，因为它决定了哪些字段是“原始识别结果”，哪些字段是“业务确认后的正式快照”，哪些字段只是“同步状态 / 拍单状态 / 调试信息”。

## 1. 解析层：`ParsedOrder`

`ParsedOrder` 是截图识别、文字整理之后得到的订单草稿类型。它偏“输入态”，不是最终持久化结构。

```python
@dataclass(frozen=True)
class ParsedOrder:
    order_id: str
    placed_at: str
    order_status: str
    product_name: str
    quantity: str
    order_amount: str
    income_amount: str
    recipient_name: str
    phone_number: str
    code: str
    address: str
    delivery_note: str
    procurement_tracking_number: str = ""
    specification: str = ""
    sku: str = ""
    sku_image_path: str = ""
    platform: str = "抖店"
    platform_fee_rate: str = ""
    platform_fee_amount: str = ""
    other_cost: str = ""
    procurement_total_cost: str = ""
    gross_profit: str = ""
    custom_cost_labels: tuple[str, str, str] = ("", "", "")
    custom_cost_values: tuple[str, str, str] = ("", "", "")
    procurement_items: tuple[ProcurementItem, ProcurementItem, ProcurementItem] = ...
```

### 字段分组

基础订单字段：

- `order_id`: 平台订单号
- `placed_at`: 下单时间，代码要求 `YYYY-MM-DD HH:MM[:SS]`
- `platform`: 平台，当前主要是 `抖店` / `微信小店`
- `order_status`: 订单状态，例如 `已发货`、`待发货`

商品字段：

- `product_name`
- `specification`
- `sku`
- `sku_image_path`
- `quantity`

收件字段：

- `recipient_name`
- `phone_number`
- `code`
- `address`
- `delivery_note`

财务字段：

- `order_amount`: 订单金额
- `income_amount`: 实收 / 收入
- `platform_fee_rate`
- `platform_fee_amount`
- `other_cost`
- `procurement_total_cost`
- `gross_profit`
- `custom_cost_labels`
- `custom_cost_values`

采购字段：

- `procurement_tracking_number`
- `procurement_items`

### 解析兼容规则

`ParsedOrder` 的来源可能是完整订单截图、抖店列表截图、微信小店截图、手机助手文字，字段完整度不一定一致。当前解析层会尽量把能识别的信息先变成可编辑草稿：

- 单订单截图：`OrderPipeline.extract_order()` 会先 OCR，再辅助整理，再解析为 `ParsedOrder`。
- 多订单列表截图：`OrderPipeline.extract_order_batch()` 会返回多条结果，录单页可切换每一单。
- 字段不完整时：如果能从文本里补出订单号、下单时间、商品、金额、收货信息等局部字段，会走 partial order fallback，不直接把整次识别判死。
- 抖店列表截图：如果顶部 `订单编号 / 订单号` 没被识别出来，但商品区识别到了 `商品单ID`，会把 `商品单ID` 当作 `order_id` 兜底。
- 微信小店虚拟号：地址提取会保留分机号语义，用 `address_snapshot.output_two` 生成“请电话送货上门谢谢【尾号】”这类备注。

这些兼容规则只发生在输入草稿层。真正写入历史后，仍以 `HistoryRow.order_snapshot` 为长期业务快照。

## 2. 采购位类型：`ProcurementItem`

```python
@dataclass(frozen=True)
class ProcurementItem:
    product_name: str
    quantity: str
    cost: str
    tracking_number: str = ""
    jd_link: str = ""
```

这是单个采购槽位的业务基础类型。

系统当前强约束：

- 采购位固定 3 个，不走动态无限数组
- 单条采购位是“商品 + 数量 + 成本 + 快递单号 + 京东链接”
- 落到历史页后，还会附加自动拍单元数据

## 3. 持久化层：`HistoryRow`

系统真正长期保存的是 `history.json` 里的行对象，不是 `ParsedOrder` 本体。

建议把它理解成：

```python
class HistoryRow(TypedDict, total=False):
    record_id: str
    shop_name: str
    status: str
    message: str
    sync_source: str
    created_at: str
    feishu_record_id: str
    feishu_result: dict[str, Any]
    order_snapshot: OrderSnapshot
    address_snapshot: AddressSnapshot
    auto_order_status: str
    auto_order_message: str
    auto_order_last_run_at: str
    auto_order_task_id: str
    auto_order_task_status: str
    auto_order_task_submitted_at: str
    auto_order_task_last_polled_at: str
    auto_order_resume_hint: str
    auto_order_debug: AutoOrderDebug
```

### 顶层字段的职责

业务标识：

- `record_id`: 历史记录主键，`HistoryStore.append()` 自动生成 UUID
- `shop_name`: 店铺名

同步结果：

- `status`: 当前同步状态，例如“已写入飞书”“写入失败”
- `message`: 同步说明 / 错误信息
- `sync_source`: 同步来源，例如人工确认、手机助手等
- `feishu_record_id`
- `feishu_result`

核心业务快照：

- `order_snapshot`
- `address_snapshot`

自动拍单状态：

- `auto_order_status`
- `auto_order_message`
- `auto_order_last_run_at`
- `auto_order_task_id`
- `auto_order_task_status`
- `auto_order_task_submitted_at`
- `auto_order_task_last_polled_at`
- `auto_order_resume_hint`
- `auto_order_debug`

关键点：

- 顶层 `status` 是“同步状态”
- `order_snapshot.order_status` 才是“订单业务状态”
- `auto_order_status` 是“自动拍单状态”

这 3 个状态不是一回事。

## 4. 业务快照层：`OrderSnapshot`

历史记录真正可编辑、可重算、可回放的核心，是 `order_snapshot`。

当前代码里它的稳定字段集合可以整理成：

```python
class OrderSnapshot(TypedDict, total=False):
    order_id: str
    placed_at: str
    platform: str
    order_status: str
    product_name: str
    specification: str
    sku: str
    sku_image_path: str
    quantity: str
    order_amount: str
    income_amount: str
    recipient_name: str
    phone_number: str
    code: str
    address: str
    delivery_note: str
    procurement_tracking_number: str
    platform_fee_rate: str
    platform_fee_amount: str
    other_cost: str
    procurement_total_cost: str
    gross_profit: str
    custom_cost_labels: list[str]
    custom_cost_values: list[str]
    after_sale_status: str
    after_sale_type: str
    after_sale_amount: str
    after_sale_date: str
    after_sale_goods_returned: str
    after_sale_resellable: str
    after_sale_note: str
    after_sale_base_income: str
    procurement_items: list[ProcurementItemSnapshot]
```

### 其中最关键的几组字段

订单事实字段：

- `order_id`
- `placed_at`
- `platform`
- `order_status`

收货与商品字段：

- `recipient_name`
- `phone_number`
- `code`
- `address`
- `product_name`
- `specification`
- `sku`
- `sku_image_path`

财务字段：

- `order_amount`
- `income_amount`
- `platform_fee_rate`
- `platform_fee_amount`
- `other_cost`
- `procurement_total_cost`
- `gross_profit`

售后字段：

- `after_sale_status`
- `after_sale_type`
- `after_sale_amount`
- `after_sale_date`
- `after_sale_goods_returned`
- `after_sale_resellable`
- `after_sale_note`
- `after_sale_base_income`

采购字段：

- `procurement_items`
- `procurement_tracking_number`

自定义成本字段：

- `custom_cost_labels`
- `custom_cost_values`

## 5. 采购快照层：`ProcurementItemSnapshot`

历史中的采购位不是纯 `ProcurementItem`，而是叠加了自动拍单状态后的版本。

```python
class ProcurementItemSnapshot(TypedDict, total=False):
    product_name: str
    quantity: str
    cost: str
    tracking_number: str
    jd_link: str
    jd_status: str
    jd_account_name: str
    jd_order_id: str
    jd_error_message: str
    jd_last_run_at: str
```

基础业务字段：

- `product_name`
- `quantity`
- `cost`
- `tracking_number`
- `jd_link`

自动拍单回写字段：

- `jd_status`
- `jd_account_name`
- `jd_order_id`
- `jd_error_message`
- `jd_last_run_at`

这意味着系统支持“一个订单 3 个采购位，每个采购位各自有独立拍单结果”。

## 6. 地址快照层：`AddressSnapshot`

```python
class AddressSnapshot(TypedDict, total=False):
    output_one: str
    output_two: str
    output_three: str
    address: str
```

实际稳定在 UI 和 `HistoryStore` 里的主字段是：

- `output_one`
- `output_two`

语义上：

- `order_snapshot.address`: 最终业务地址
- `address_snapshot.output_one`: 地址提取结果一
- `address_snapshot.output_two`: 地址提取结果二 / 补充备注

这层存在的意义不是重复保存地址，而是保留“提取过程结果”，方便后面人工复核和自动拍单拼装。

## 7. 自动拍单类型

### `AutoOrderRequest`

```python
@dataclass(frozen=True)
class AutoOrderRequest:
    history_record_id: str
    source: str
    shop_name: str
    recipient_name: str
    phone_number: str
    address: str
    delivery_note: str
    address_output_one: str
    address_output_two: str
    procurement_indices: tuple[int, ...]
    procurement_items: tuple[dict[str, Any], ...]
    jd_accounts: tuple[dict[str, Any], ...]
```

重点：

- 自动拍单不是直接拿 `ParsedOrder`
- 它消费的是“历史记录 + 地址输出 + 指定采购位 + 京东账号集”

### `AutoOrderItemResult`

```python
@dataclass(frozen=True)
class AutoOrderItemResult:
    procurement_index: int
    status: str
    account_name: str = ""
    jd_order_id: str = ""
    error_message: str = ""
    last_run_at: str = ""
```

### `AutoOrderResult`

```python
@dataclass(frozen=True)
class AutoOrderResult:
    order_status: str
    message: str
    last_run_at: str
    item_results: tuple[AutoOrderItemResult, ...]
```

### `AutoOrderTaskTicket / AutoOrderTaskSnapshot`

适合异步桥接场景：

- `AutoOrderTaskTicket`: 提交任务后的票据
- `AutoOrderTaskSnapshot`: 轮询中的任务状态快照

这层把“提交任务”和“拿到每个采购位结果”拆开了。

## 8. 财务字段的派生规则

代码里有一条很重要的原则：财务字段不是随便填的，它们可以被重算。

### 平台扣点金额

来源：

- `income_amount`
- `platform_fee_rate`

规则：

- `platform_fee_rate` 支持 `0.06` 和 `6` 两种写法
- 内部统一转成乘数后计算

### 采购总成本

规则：

- `sum(quantity * cost for procurement_items)`

### 毛利润

规则：

```text
gross_profit
= income_amount
- platform_fee_amount
- procurement_total_cost
- other_cost
- 自定义成本合计
```

### 售后影响

当订单进入 `已完成售后` 且售后类型属于退款类时：

- `income_amount` 会按 `after_sale_base_income - after_sale_amount` 重算
- 若是 `退货退款` 且“货已收回”，采购总成本可被归零

也就是说，售后不是只多挂几个备注字段，而是真的会回写利润口径。

## 9. 飞书载荷不是订单类型本身

`build_feishu_payload()` 会把 `ParsedOrder` 转成飞书字段映射后的 payload。

它的特点：

- 不是系统内标准订单对象
- 是“订单对象 + 店铺名 + 同步状态 + 字段映射”拼出来的外部输出对象
- 字段名可以和飞书表头自定义映射

所以：

- `ParsedOrder` 是内部业务类型
- 飞书 payload 是外部集成类型

不要反过来拿飞书 payload 当内部标准模型。

## 10. 这套类型设计能帮你避免什么坑

### 1. 避免把“订单状态”“同步状态”“拍单状态”混成一个字段

系统明确拆成：

- `order_snapshot.order_status`
- `row.status`
- `row.auto_order_status`

这样可以避免出现这种混乱：

- 订单已经 `已发货`
- 但飞书写入失败
- 自动拍单又是 `部分成功`

如果只留一个 `status`，后面根本无法判断到底是哪一步出了问题。

### 2. 避免把 OCR 草稿直接当成最终真相

`ParsedOrder` 只负责“识别结果”。
真正长期保存的是 `HistoryRow -> order_snapshot`。

这样可以避免：

- 一次 OCR 误识别直接污染正式订单
- 后续人工修订没有正式承载层
- 再次同步时丢失人工修订内容

### 3. 避免历史兼容性崩掉

`HistoryStore._normalize_row()` 会兼容老的扁平行结构，把旧数据补成：

- `order_snapshot`
- `address_snapshot`
- `auto_order_*`

这能避免你以后一改结构，旧历史直接全部打不开。

### 4. 避免采购位数量漂移

系统把采购位固定成 3 槽，并统一 `normalize_procurement_items(size=3)`。

好处：

- UI 渲染稳定
- 自动拍单索引稳定
- 飞书 1/2/3 采购字段稳定

否则最容易出现：

- 某次是 1 条采购
- 某次是 2 条采购
- 某次历史里少数组项
- 自动拍单结果回写错位

### 5. 避免利润字段手填后越来越假

系统把：

- 平台扣点金额
- 采购总成本
- 毛利润
- 售后后的净收入

都收敛到一套重算逻辑里。

这能避免：

- 改了收入忘了改扣点
- 改了采购成本忘了改毛利润
- 售后退款后利润还是老数

### 6. 避免售后只记“备注”，不进财务口径

售后字段单独存在，而且会参与财务重算。

这能避免一个常见坑：

- 订单表面看是赚了
- 实际已经退款或部分退款
- 但利润表还按原收入算

### 7. 避免地址清洗把原始识别过程抹掉

系统保留两层：

- `order_snapshot.address`: 最终业务地址
- `address_snapshot.output_one/output_two`: 提取过程结果

这样你既能拿到干净地址，也不会丢掉地址提取链路。

### 8. 避免自动拍单“只看整单结果”，看不到局部失败

采购位有自己的：

- `jd_status`
- `jd_order_id`
- `jd_error_message`

整单再汇总成：

- `auto_order_status`
- `auto_order_message`

这能避免：

- 一个订单 3 个采购位
- 其中 2 个成功、1 个失败
- 最后只能看到“失败”或“成功”，不知道卡在哪个采购位

### 9. 避免把外部平台字段名绑死在内部模型上

内部用 `ParsedOrder / OrderSnapshot`，
飞书输出再走 `field_mapping`。

这能避免：

- 飞书列名一改，系统模型全跟着改
- 多店铺字段表头不一致时整个系统失效

### 10. 避免“修一处，别处没跟上”

当前结构本质上把数据拆成了：

- 事实字段
- 派生字段
- 集成字段
- 执行状态字段

这让后续改动更容易局部化。比如你改利润算法，重点只会落在财务重算；你改飞书字段，不需要动历史结构；你改自动拍单桥接，不需要重做订单识别模型。

## 11. 你后面最值得继续守住的边界

如果你后面继续扩系统，我建议死守这 4 条：

1. `ParsedOrder` 只做输入草稿，不做长期真相。
2. `HistoryRow` 顶层只放流程状态和元信息，业务数据都收进 `order_snapshot`。
3. 财务字段能重算就不要手工散落维护。
4. 自动拍单状态永远保留“整单汇总 + 采购位明细”两层。

## 12. 一个实用结论

如果你要把这套系统再抽象成更正式的开发约束，可以直接把它理解成：

- `ParsedOrder`: 输入 DTO
- `OrderSnapshot`: 订单领域快照
- `HistoryRow`: 持久化聚合根
- `ProcurementItemSnapshot`: 子实体
- `AutoOrder*`: 执行编排状态

这样你后面无论接飞书、接手机助手、接真实自动拍单服务，结构都不会乱掉。
