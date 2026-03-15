# Structured Output Schema

`xhs-cli` uses a shared agent-friendly envelope for machine-readable output.

## Success

```yaml
ok: true
schema_version: "1"
data: ...
```

## Error

```yaml
ok: false
schema_version: "1"
error:
  code: not_authenticated
  message: need login
```

## Notes

- `--json-output` uses this envelope
- Common `error.code` values: `not_authenticated`, `mcp_error`, `cdp_error`, `api_error`
