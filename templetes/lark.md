# templete lark

```
| Task ID | Task Name | Task Link | Type |
| --- | --- | --- | --- |
| <id> | <title> | <link> | <type = Task|Bug|User Story> |
...
```

## Quy ước

- Link dạng `<server>/<org>/<project>/_workitems/edit/<id>`
- Title giữ nguyên từ TFS; ký tự `|` trong title phải escape `\|`
- Type lấy từ `System.WorkItemType`
