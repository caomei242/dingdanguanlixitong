# 历史改单覆盖飞书 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让历史记录在修改后自动覆盖飞书原记录，并支持双重确认后同时删除本地历史与飞书记录。

**Architecture:** 在现有历史快照里标准化保存 `feishu_record_id`，提交链路根据是否存在该 ID 选择更新或新增；删除链路增加确认状态与飞书删除任务。首次写入仍走新增，但会把飞书返回的 `record_id` 固化到历史中，后续 `保存修改` 直接复用这条绑定关系。

**Tech Stack:** PySide6、requests、pytest、pytest-qt、现有 `HistoryStore`/`FeishuClient`/`MainWindow`

---

### Task 1: 为飞书客户端补齐更新与删除能力

**Files:**
- Modify: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/src/strawberry_order_management/services/feishu_client.py`
- Test: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/test_pipeline.py`

- [ ] **Step 1: 写更新/删除接口的失败测试**

```python
def test_feishu_client_update_record_uses_put(monkeypatch):
    ...
    result = client.update_record("access_token", "rec_123", {"备注": "ok"})
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/records/rec_123")


def test_feishu_client_delete_record_uses_delete(monkeypatch):
    ...
    result = client.delete_record("access_token", "rec_123")
    assert captured["method"] == "DELETE"
    assert captured["url"].endswith("/records/rec_123")
```

- [ ] **Step 2: 运行测试确认先失败**

Run: `python3 -m pytest tests/test_pipeline.py -k "update_record or delete_record" -q`
Expected: FAIL，提示 `FeishuClient` 缺少 `update_record`/`delete_record`

- [ ] **Step 3: 实现最小代码**

在 `FeishuClient` 中新增：

```python
def update_record(self, access_token: str, record_id: str, fields: dict) -> dict:
    ...

def delete_record(self, access_token: str, record_id: str) -> dict:
    ...
```

并补 `_request_json(method, ...)` 统一复用请求与错误解析。

- [ ] **Step 4: 重新运行测试确认通过**

Run: `python3 -m pytest tests/test_pipeline.py -k "update_record or delete_record" -q`
Expected: PASS


### Task 2: 先用测试锁定历史保存后自动覆盖飞书

**Files:**
- Modify: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/ui/test_main_window.py`
- Possibly modify: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/test_history_store.py`

- [ ] **Step 1: 写“保存修改时走更新”的失败测试**

```python
def test_history_save_updates_existing_feishu_record(qtbot, tmp_path, monkeypatch):
    ...
    row["feishu_record_id"] = "rec_123"
    ...
    page.save_button.click()
    qtbot.waitUntil(lambda: captured["updated"])
    assert captured["updated"][0]["record_id"] == "rec_123"
```

- [ ] **Step 2: 写“原记录不存在时自动补建”的失败测试**

```python
def test_history_save_recreates_record_when_original_missing(qtbot, tmp_path, monkeypatch):
    ...
    update_record -> raise ValueError("飞书写入失败：record not found")
    create_record -> return {"data": {"record_id": "rec_new"}}
    ...
    assert updated_row["feishu_record_id"] == "rec_new"
```

- [ ] **Step 3: 写“首次写入后保存 feishu_record_id”的失败测试**

```python
def test_submit_persists_feishu_record_id_into_history(...):
    ...
    assert record["feishu_record_id"] == "rec_123"
```

- [ ] **Step 4: 跑目标测试确认先失败**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_main_window.py -k "feishu_record_id or updates_existing_feishu_record or recreates_record_when_original_missing" -q`
Expected: FAIL


### Task 3: 实现历史自动覆盖同步与补建回退

**Files:**
- Modify: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/src/strawberry_order_management/ui/main_window.py`
- Modify: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/src/strawberry_order_management/history.py`（如果需要标准化字段）

- [ ] **Step 1: 在历史快照中固化飞书 record_id**

在 `_build_history_snapshot`、`_handle_submit_success` 中提取：

```python
def _extract_feishu_record_id(response: dict) -> str:
    return str(response.get("data", {}).get("record_id", "")).strip()
```

并把 `feishu_record_id` 写入历史行。

- [ ] **Step 2: 让 `保存修改` 自动触发飞书同步**

在 `_handle_history_save_request` 中：

```python
self._update_history_snapshot(record_id, patch)
row = self._history_store.get(record_id)
task = self._build_feishu_submission_task(self._build_payload_from_history_row(row))
task["history_record_id"] = record_id
task["mode"] = "update_or_create"
task["feishu_record_id"] = row.get("feishu_record_id", "")
self._start_submit_job(task)
```

- [ ] **Step 3: 在提交 worker 中支持 update-or-create**

```python
if task["mode"] == "update_or_create" and task.get("feishu_record_id"):
    try:
        response = client.update_record(...)
        action = "updated"
    except ValueError as exc:
        if _is_missing_record_error(str(exc)):
            response = client.create_record(...)
            action = "created_after_missing"
        else:
            raise
else:
    response = client.create_record(...)
```

- [ ] **Step 4: 在成功回调里更新历史绑定**

把新的 `feishu_record_id`、`status`、`message`、`feishu_result` 写回同一条历史。

- [ ] **Step 5: 跑目标测试确认通过**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_main_window.py -k "feishu_record_id or updates_existing_feishu_record or recreates_record_when_original_missing" -q`
Expected: PASS


### Task 4: 历史删除加入双重确认与飞书删除

**Files:**
- Modify: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/src/strawberry_order_management/ui/pages/history_page.py`
- Modify: `/Users/gd/Desktop/d/.worktrees/strawberry_order_management-v1/src/strawberry_order_management/ui/main_window.py`
- Test: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/ui/test_history_page.py`
- Test: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/ui/test_main_window.py`

- [ ] **Step 1: 写删除双确认的失败测试**

```python
def test_history_delete_requires_two_confirms_before_remote_delete(...):
    ...
    assert delete_remote_called is True
    assert local_row_removed is True
```

- [ ] **Step 2: 写“只删本地”与“远端不存在仍删本地”的测试**

```python
def test_history_delete_local_only_when_second_confirm_declined(...):
    ...

def test_history_delete_keeps_local_delete_when_remote_record_missing(...):
    ...
```

- [ ] **Step 3: 运行目标测试确认失败**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py -k "delete" -q`
Expected: FAIL

- [ ] **Step 4: 实现最小 UI 与逻辑**

在 `HistoryPage` 中新增删除确认状态信号或回调参数，在 `MainWindow` 中：

```python
def _handle_history_delete_request(self, record_id: str, delete_remote: bool) -> None:
    ...
```

若 `delete_remote` 且存在 `feishu_record_id`，先调 `delete_record`，再删本地；若记录不存在，写提示后继续删本地。

- [ ] **Step 5: 运行目标测试确认通过**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py -k "delete" -q`
Expected: PASS


### Task 5: 回归与收口

**Files:**
- Modify as needed from previous tasks
- Test: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/test_*.py`
- Test: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/ui/test_history_page.py`
- Test: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/ui/test_main_window.py`
- Test: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/ui/test_settings_page.py`
- Test: `/Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1/tests/ui/test_intake_page.py`

- [ ] **Step 1: 跑非 UI 测试**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_*.py -q`
Expected: PASS

- [ ] **Step 2: 跑核心 UI 测试**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py tests/ui/test_settings_page.py tests/ui/test_intake_page.py -q`
Expected: PASS（如遇既有 Qt 段错误，则拆分子集验证并记录）

- [ ] **Step 3: 提交代码**

```bash
git add src/strawberry_order_management/services/feishu_client.py \
        src/strawberry_order_management/ui/main_window.py \
        src/strawberry_order_management/ui/pages/history_page.py \
        tests/test_pipeline.py \
        tests/ui/test_history_page.py \
        tests/ui/test_main_window.py
git commit -m "feat: overwrite feishu records from history edits"
```

