# templete lark

```
| Status | Start date | End date | OT | Note | Type | Task ID | Task Name | Task Link |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <status> | <start date> | <end date> | <ot> | <note> | <type> | <taskid>  | <task name> | <task link> |
...
```

## Quy ước

- Start date / End date theo định dạng `yyyy-mm-dd` (vd `2026-08-19`)
- Link dạng `<server>/<org>/<project>/_workitems/edit/<id>`
- Title giữ nguyên từ TFS; ký tự `|` trong title phải escape `\|`
- Type lấy từ `System.WorkItemType`
