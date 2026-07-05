# Scanner Integration

The scanner module is currently a stub. It defines the boundary where local scanner communication will be added later.

## Current File

```text
app/scanner/client.py
```

## Current Interface

```python
async def scan_document() -> bytes
```

The method is expected to return raw bytes for a scanned document. It currently raises `NotImplementedError`.

## Future Implementation Notes

When scanner behavior is implemented:

- Keep device-specific code inside `app/scanner/`.
- Do not call scanner libraries directly from API routes.
- Convert scanner exceptions into application-level errors in the service layer.
- Add configuration for scanner device name, resolution, color mode, and output format only when needed.
- Add integration tests around the scanner adapter with hardware calls mocked.

## MVP Constraint

No real scanner communication is included in this skeleton.

