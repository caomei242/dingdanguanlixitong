# 爱马仕手机助手接入草莓订单系统

## 目标

让手机微信里的爱马仕负责对话，草莓订单管理系统负责识别和落草稿。

第一版只做“待确认草稿”：

- 可以返回 `结果一` / `结果二`
- 可以创建历史订单里的待确认草稿
- 不直接写飞书
- 不自动拍单

## 推荐对话方式

你在手机微信里发给爱马仕：

```text
录一单
订单文字或订单截图
```

爱马仕收到后调用草莓系统本地接口。

## 接口

预览接口：

```text
POST http://127.0.0.1:9020/mobile/orders/preview
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

创建草稿接口：

```text
POST http://127.0.0.1:9020/mobile/orders/drafts
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

多单预览接口：

```text
POST http://127.0.0.1:9020/mobile/orders/preview-batch
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

多单创建草稿接口：

```text
POST http://127.0.0.1:9020/mobile/orders/drafts-batch
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

## 请求体

文字订单：

```json
{
  "text": "张三13800138000浙江省杭州市...",
  "shop_name": "",
  "platform": ""
}
```

图片订单：

```json
{
  "text": "",
  "image_base64": "<图片base64>",
  "shop_name": "",
  "platform": ""
}
```

如果爱马仕能先把微信图片保存到电脑本地，也可以传：

```json
{
  "text": "",
  "image_path": "/absolute/path/to/order-image.png",
  "shop_name": "",
  "platform": ""
}
```

多单创建草稿时可以传 `selected_indexes`，只创建选中的订单；不传时默认创建所有已识别成功且历史中不存在同订单号的订单：

```json
{
  "text": "",
  "image_base64": "<图片base64>",
  "shop_name": "",
  "platform": "",
  "selected_indexes": [1, 2]
}
```

字段优先级：

- 请求里传了 `shop_name / platform`，就使用请求值。
- 没传时按草莓系统设置里的平台默认规则处理：
  - 先取 `录单默认平台`
  - 再取该平台对应的默认店铺（`抖店默认店铺` 或 `微信默认店铺`）
- 手机入口只创建 `待确认` 草稿，不直接写飞书、不自动拍单。

## 返回给用户的话术

默认只回复两行，方便手机直接复制：

```text
结果一：<output_one>
结果二：<output_two>
```

如果用户明确问草稿编号、缺失字段或是否创建草稿，再补充这些信息。

## 爱马仕系统提示词

```text
你是草莓订单管理系统的手机助手入口。

用户会在手机微信里发订单文字或订单截图给你。你不要自己直接写飞书，也不要自动拍单。你的任务是调用草莓订单管理系统的本地 HTTP 接口，把订单信息交给草莓系统识别，并把结果一、结果二和草稿编号返回给用户。

规则：
1. 单订单默认先调用 /mobile/orders/drafts 创建待确认草稿；一张图里有多单时调用 /mobile/orders/drafts-batch。
2. 请求必须带 Authorization: Bearer <API_KEY>。
3. 如果用户只想看识别结果，不想创建草稿，单订单调用 /mobile/orders/preview，多订单调用 /mobile/orders/preview-batch。
4. 文字放到 text 字段。
5. 图片优先转成 image_base64；如果图片已经在电脑本地，也可以传 image_path。
6. shop_name 和 platform 有明确值就传，没有就留空，让草莓系统走平台默认规则。
7. 单订单默认回复只允许两行：结果一、结果二；多订单按“第1单结果一 / 第1单结果二 / 第2单结果一 / 第2单结果二”输出。不要追加默认店铺、默认平台、缺失字段或说明文字。
8. 如果用户明确问缺失字段，再提醒用户回电脑补齐。
9. 不允许说“已写入飞书”，除非草莓系统明确返回飞书写入结果。
10. 不允许说“已自动拍单”，除非草莓系统明确返回自动拍单成功。
11. 收到图片时，必须调用草莓系统图片识别能力，不要自己用视觉能力代替草莓系统。
12. 如果草莓系统返回多单结果，只输出每单的结果一和结果二；不要夹杂英文总结。
```

## 爱马仕本机技能

已在爱马仕技能目录新增：

```text
/Users/gd/.hermes/skills/strawberry-mobile-helper/SKILL.md
```

爱马仕可直接调用这个本机工具，不需要在对话里暴露 API Key：

```bash
/Users/gd/.local/bin/strawberry-mobile-helper preview --text "订单文字" --address-lines
/Users/gd/.local/bin/strawberry-mobile-helper draft --text "订单文字" --address-lines
/Users/gd/.local/bin/strawberry-mobile-helper preview --batch --text "多单订单文字" --address-lines
/Users/gd/.local/bin/strawberry-mobile-helper draft --batch --text "多单订单文字" --address-lines
```

如果图片已经落到电脑本地：

```bash
/Users/gd/.local/bin/strawberry-mobile-helper draft --batch --image-path "/absolute/path/to/image.png" --address-lines
/Users/gd/.local/bin/strawberry-mobile-helper draft --batch --image-file-as-base64 "/absolute/path/to/image.png" --address-lines
```

## 本地准备

当前电脑已配置为后台常驻入口：

- 本地页面：`http://127.0.0.1:9020/mobile`
- 预览接口：`http://127.0.0.1:9020/mobile/orders/preview`
- 草稿接口：`http://127.0.0.1:9020/mobile/orders/drafts`
- 默认规则以草莓系统设置页为准：`录单默认平台 + 抖店默认店铺 + 微信默认店铺`
- 后台日志：`/Users/gd/.config/strawberry-order-management/logs/mobile-helper.out.log`

如果后面需要在草莓订单管理系统里手动调整：

1. 打开 `设置`
2. 找到 `手机助手入口`
3. 填写 `API Key`
4. 启用入口
5. 点击 `启动`
6. 爱马仕和草莓系统在同一台电脑上时，地址使用 `http://127.0.0.1:9020`

如果爱马仕运行在另一台设备，需要把 `Host` 改成电脑局域网 IP，并确保网络可访问。

## 后台服务

手机助手入口由 macOS LaunchAgent 常驻：

```text
/Users/gd/Library/LaunchAgents/com.strawberry.mobile-helper.plist
```

如果修改了手机助手相关代码，需要重新同步运行副本并重启后台服务。

## 识别与排障

- 图片识别会复用电脑端草莓系统当前配置的 OCR；如果启用了 MiniMax MCP OCR，会调用 MCP 的 `understand_image`，不是让爱马仕自己看图。
- MCP OCR 单次响应有 90 秒超时，超时会返回中文提示；通常可以直接重试。
- 抖店列表截图如果顶部 `订单编号 / 订单号` 没被 OCR 识别出来，但商品区识别到了 `商品单ID`，草莓系统会用 `商品单ID` 兜底生成订单号。
- 如果返回 `missing_fields`，代表草稿信息不完整，但仍可回电脑在历史订单里人工补齐。
- 多单接口会跳过历史里已经存在的同订单号，避免重复创建草稿。
- 手机入口只负责识别和落草稿；真正写飞书时，如果飞书表里缺少旧字段映射，桌面端会自动跳过缺失字段并提示，不需要为了这件事重建整张表。
