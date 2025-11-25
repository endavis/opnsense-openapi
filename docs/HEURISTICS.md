# Heuristic Schema Generation Guide

## Quick Reference

This document provides a quick reference for understanding and extending the heuristic-based response schema generation system.

## Pattern Matching Rules

### Priority Order (First Match Wins)

```
1. Service Actions      → {"response": string} or {"status": enum}
2. Boolean Queries      → {"enabled": boolean}
3. Statistics          → {additionalProperties: true}
4. Special Operations  → StatusResponse
5. Export/Query        → {additionalProperties: true}
6. List Operations     → Paginated or dynamic object
7. Model-Based         → Model schemas (search/get/add/set/del)
8. Fallback           → Generic schemas
```

## Pattern Catalog

### 1. Service Control Actions

**Triggers**: `start`, `stop`, `restart`, `reconfigure`, `status`

**From**: `ApiMutableServiceControllerBase` inherited methods

| Action | Response | Required Fields |
|--------|----------|----------------|
| `start`, `stop`, `restart` | `{"response": "string"}` | `response` |
| `reconfigure` | `{"status": "ok"\|"failed"}` | `status` |
| `status` | `{"status": enum, "widget": object}` | `status` |

**Examples**:
- `/api/openvpn/service/startService` → `{"response": "..."}`
- `/api/unbound/service/reconfigure` → `{"status": "ok"}`
- `/api/nginx/service/status` → `{"status": "running"}`

**Code Location**: Line 261-300 in `openapi_generator.py`

### 2. Boolean Query Patterns

**Triggers**: `isenabled` (case-insensitive, ignores underscores)

**Response**:
```json
{
  "type": "object",
  "properties": {
    "enabled": {"type": "boolean"}
  }
}
```

**Examples**:
- `/api/firewall/filter/isEnabled`
- `/api/dhcpv4/service/is_enabled`

**Code Location**: Line 301-313

### 3. Statistics & Information

**Triggers**: `stats`, `info`, `overview`, `summary`

**Response**:
```json
{
  "type": "object",
  "additionalProperties": true,
  "description": "Statistics or information object"
}
```

**Examples**:
- `/api/diagnostics/interface/getInterfaceStatistics`
- `/api/system/info/overview`

**Code Location**: Line 314-325

### 4. Special Operations

**Triggers**: `apply`, `flush`, `revert`, `savepoint`, `rollback`, `upload`, `generate`, `kill`, `disconnect`, `connect`

**Response**: `StatusResponse` reference

```json
{
  "$ref": "#/components/schemas/StatusResponse"
}
```

**StatusResponse Definition**:
```json
{
  "type": "object",
  "properties": {
    "result": {"type": "string", "example": "saved"},
    "validations": {"type": "object"}
  }
}
```

**Examples**:
- `/api/firewall/filter/apply`
- `/api/captiveportal/session/killSession/{uuid}`
- `/api/openvpn/instances/genKey`

**Code Location**: Line 326-331

### 5. Export & Query Operations

**Triggers**: `export`, `download`, `rawdump`, `dump`, `providers`, `accounts`, `templates`

**Response**:
```json
{
  "type": "object",
  "additionalProperties": true,
  "description": "Export data or file content"
}
```

**Examples**:
- `/api/firewall/alias/export`
- `/api/openvpn/export/providers`
- `/api/diagnostics/log/download`

**Code Location**: Line 332-343

### 6. List Operations

**Triggers**: `list`, `aliases`, `countries`, `groups`, `users`, `categories`

**With Model**:
```json
{
  "$ref": "#/components/schemas/{ModelName}Search"
}
```

**Without Model**:
```json
{
  "type": "object",
  "additionalProperties": true,
  "description": "Object with dynamic keys or array of items"
}
```

**Examples**:
- `/api/firewall/alias_util/aliases` → Dynamic object
- `/api/system/users/list` (with model) → Paginated
- `/api/diagnostics/interface/listCountries` → Dynamic object

**Code Location**: Line 344-363

### 7. Model-Based Patterns

**Requires**: XML model file exists in `models/OPNsense/{Module}/{Controller}.xml`

#### Search & Find

**Triggers**: `search`, `find`, or action ending with `item` (e.g., `searchItem`, `getItem`)

**Response**:
```json
{
  "$ref": "#/components/schemas/{ModelName}Search"
}
```

**Search Schema Structure**:
```json
{
  "type": "object",
  "properties": {
    "current": {"type": "integer", "example": 1},
    "rowCount": {"type": "integer", "example": 10},
    "total": {"type": "integer", "example": 50},
    "rows": {
      "type": "array",
      "items": {"$ref": "#/components/schemas/{ModelName}"}
    }
  }
}
```

**Examples**:
- `/api/firewall/alias/search`
- `/api/firewall/filter/searchItem`
- `/api/ids/settings/findRule`

**Code Location**: Line 364-374

#### Get Operations

**Triggers**: `get` in action name

**Response**:
```json
{
  "type": "object",
  "properties": {
    "{controller_lowercase}": {
      "$ref": "#/components/schemas/{ModelName}"
    }
  }
}
```

**Example**:
```
Action: /api/firewall/alias/get/{uuid}
Response: {
  "alias": {
    "name": "...",
    "type": "...",
    "enabled": "..."
  }
}
```

**Code Location**: Line 375-388

#### Mutation Operations

**Triggers**: `add`, `set`, `del`, `toggle`, `update`

**Response**: `StatusResponse`

**Request Body** (for add/set/update):
```json
{
  "type": "object",
  "properties": {
    "{controller_lowercase}": {
      "$ref": "#/components/schemas/{ModelName}"
    }
  }
}
```

**Examples**:
- `/api/firewall/alias/addItem` → POST with alias data, returns StatusResponse
- `/api/firewall/alias/setItem/{uuid}` → POST with alias data, returns StatusResponse
- `/api/firewall/alias/delItem/{uuid}` → POST, returns StatusResponse

**Code Location**: Line 389-407

### 8. Fallback Patterns (No Model)

When no model exists but action matches common patterns:

| Pattern | Response | Request Body |
|---------|----------|--------------|
| `search`, `find`, `*item` | Generic paginated | None |
| `get` | Generic object | None |
| `add`, `set`, `update`, `delete`, `remove`, `toggle` | StatusResponse | Generic object |

**Generic Paginated Response**:
```json
{
  "type": "object",
  "properties": {
    "current": {"type": "integer"},
    "rowCount": {"type": "integer"},
    "total": {"type": "integer"},
    "rows": {"type": "array", "items": {"type": "object"}}
  }
}
```

**Code Location**: Line 408-455

## UUID Path Parameter Detection

**Heuristic Algorithm**:
```python
has_verb = any(verb in action_lower
               for verb in ['get', 'set', 'del', 'toggle', 'start',
                           'stop', 'restart', 'kill', 'drop',
                           'disconnect', 'connect'])

has_noun = any(noun in action_lower
               for noun in ['item', 'rule', 'server', 'client',
                           'job', 'route', 'alias', 'certificate',
                           'ca', 'session', 'key', 'vessel'])

is_exception = any(exc in action_lower
                   for exc in ['add', 'search', 'list', 'match',
                              'export', 'import', 'options'])

requires_uuid = has_verb AND has_noun AND NOT is_exception
```

**Path Generation**:
```
Without UUID: /api/{module}/{controller}/{action}
With UUID:    /api/{module}/{controller}/{action}/{uuid}
```

**UUID Parameter Schema**:
```json
{
  "name": "uuid",
  "in": "path",
  "required": true,
  "schema": {"type": "string", "format": "uuid"},
  "description": "Unique ID of the resource"
}
```

**Examples**:

| Action | Path | UUID? | Reason |
|--------|------|-------|--------|
| `getItem` | `/api/firewall/alias/getItem/{uuid}` | ✅ | verb + noun |
| `setRule` | `/api/firewall/filter/setRule/{uuid}` | ✅ | verb + noun |
| `deleteServer` | `/api/proxy/server/deleteServer/{uuid}` | ✅ | verb + noun |
| `searchItem` | `/api/firewall/alias/searchItem` | ❌ | exception |
| `addItem` | `/api/firewall/alias/addItem` | ❌ | exception |
| `list` | `/api/firewall/alias/list` | ❌ | no verb+noun |

**Code Location**: Line 228-254

## Adding New Heuristics

### Step-by-Step Guide

#### 1. Identify the Pattern

Analyze OPNsense controllers to find common patterns:

```bash
# Find all actions with a specific pattern
grep -r "public function.*Action" tmp/opnsense_source/25.7.6/src/opnsense/mvc/app/controllers/ \
  | grep -i "validate" \
  | head -10
```

#### 2. Examine Response Structure

Look at actual PHP implementations:

```bash
# View a specific controller
cat tmp/opnsense_source/25.7.6/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/AliasController.php
```

#### 3. Determine Priority

Choose where in the hierarchy:
- **Before Model-Based**: For generic patterns that override model behavior
- **After Model-Based**: For fallback patterns

#### 4. Add Pattern Detection

**File**: `src/opnsense_openapi/generator/openapi_generator.py`

**Location**: In `_add_path_to_spec` method

```python
# Add after line 343 (after DOWNLOAD/DUMP PATTERNS)
# Add before line 344 (before LIST PATTERNS)

# === VALIDATION PATTERNS ===
elif 'validate' in act_lower or 'check' in act_lower:
    # Validation endpoints return validation results
    response_schema["content"] = {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "valid": {"type": "boolean", "description": "Validation result"},
                    "errors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Validation error messages"
                    }
                },
                "required": ["valid"]
            }
        }
    }
```

#### 5. Test the Pattern

```bash
# Regenerate spec
uv run opnsense-openapi generate 25.7.6

# Check if pattern is matched
python3 << 'EOF'
import json
with open('src/opnsense_openapi/specs/opnsense-25.7.6.json') as f:
    spec = json.load(f)

# Find validate endpoints
for path, methods in spec['paths'].items():
    if 'validate' in path.lower():
        has_schema = methods['post']['responses']['200'].get('content') is not None
        print(f"{'✅' if has_schema else '❌'} {path}")
EOF
```

#### 6. Update Tests

Add test case to `tests/test_openapi_generator.py`:

```python
def test_validation_pattern() -> None:
    """Test validation pattern detection."""
    controller = ApiController(
        module="Test",
        controller="Validator",
        base_class="ApiControllerBase",
        endpoints=[
            ApiEndpoint(
                name="validateConfig",
                method="POST",
                description="Validate configuration",
                parameters=[]
            )
        ],
    )

    with TemporaryDirectory() as tmpdir:
        generator = OpenApiGenerator(Path(tmpdir))
        spec_path = generator.generate([controller], "24.7")

        with spec_path.open() as f:
            spec = json.load(f)

        path_op = spec["paths"]["/api/test/validator/validateConfig"]["post"]
        schema = path_op["responses"]["200"]["content"]["application/json"]["schema"]

        assert "valid" in schema["properties"]
        assert "errors" in schema["properties"]
```

#### 7. Document the Pattern

Add to this document's Pattern Catalog section.

### Example: Adding Stream/SSE Pattern

**1. Identify Pattern**:
```bash
grep -r "streamAction\|sseAction" tmp/opnsense_source/25.7.6/
```

**2. Examine Response**:
```php
public function streamAction()
{
    // SSE endpoint - returns text/event-stream
    return $this->streamResponse();
}
```

**3. Add Detection**:
```python
# === STREAM/SSE PATTERNS ===
elif 'stream' in act_lower or 'sse' in act_lower:
    # Streaming endpoints return event-stream
    response_schema["content"] = {
        "text/event-stream": {
            "schema": {
                "type": "string",
                "description": "Server-Sent Events stream"
            }
        }
    }
```

## Pattern Testing Checklist

When adding a new pattern, verify:

- [ ] Pattern matches intended endpoints
- [ ] Pattern doesn't override higher-priority patterns unintentionally
- [ ] Response schema matches actual API responses
- [ ] Request body schema (if applicable) is correct
- [ ] UUID detection works correctly
- [ ] Test case added
- [ ] Documentation updated
- [ ] Coverage improvement verified

## Common Pitfalls

### 1. Pattern Too Broad

**Problem**: Pattern matches unintended endpoints

**Example**:
```python
# BAD: Matches everything with "get"
if 'get' in act_lower:
    # ...
```

**Solution**: Be more specific
```python
# GOOD: More restrictive
if act_lower.startswith('get') or act_lower == 'get':
    # ...
```

### 2. Wrong Priority Order

**Problem**: Lower priority pattern never matches

**Example**: Adding list pattern AFTER model-based patterns means `listUsers` with a model will match model pattern first.

**Solution**: Place specific patterns before generic ones.

### 3. Missing Edge Cases

**Problem**: Pattern works for singular but not plural

**Example**: `item` but not `items`

**Solution**: Test variations
```python
if act_lower.endswith('item') or act_lower.endswith('items'):
    # ...
```

### 4. Conflicting Patterns

**Problem**: Two patterns match the same endpoint

**Example**: `downloadStats` matches both "download" and "stats"

**Solution**: Order matters - first match wins. Place more specific pattern first.

## Debugging Heuristics

### Check Pattern Matching

```python
# Add debug logging in openapi_generator.py
import logging
logger = logging.getLogger(__name__)

# In _add_path_to_spec method
logger.debug(f"Processing {module}/{controller}/{action}")
logger.debug(f"Action (lower): {act_lower}")
logger.debug(f"Has model: {schema_name is not None}")
logger.debug(f"Requires UUID: {requires_uuid}")
```

Run with debug logging:
```bash
PYTHONLOG=DEBUG uv run opnsense-openapi generate 25.7.6 2>&1 | grep "Processing"
```

### Analyze Coverage Gaps

```python
# Find endpoints without schemas
import json

with open('src/opnsense_openapi/specs/opnsense-25.7.6.json') as f:
    spec = json.load(f)

missing = []
for path, methods in spec['paths'].items():
    if not methods['post']['responses']['200'].get('content'):
        action = path.split('/')[-1]
        missing.append((path, action))

# Group by action pattern
from collections import Counter
patterns = Counter(action for _, action in missing)
print("Top 10 unmatched patterns:")
for pattern, count in patterns.most_common(10):
    print(f"  {pattern}: {count}")
    # Show example paths
    examples = [path for path, act in missing if act == pattern][:2]
    for ex in examples:
        print(f"    {ex}")
```

### Verify Generated Schema

```bash
# Use swagger validator
npm install -g @apidevtools/swagger-cli

# Validate spec
swagger-cli validate src/opnsense_openapi/specs/opnsense-25.7.6.json
```

## Performance Considerations

### Pattern Matching Efficiency

Current implementation uses string matching which is O(n) for each pattern check.

**Optimization opportunity** (if needed):
```python
# Instead of multiple if/elif checks
if 'start' in act_lower or 'stop' in act_lower:
    # ...

# Use set lookup (O(1))
SERVICE_ACTIONS = {'start', 'stop', 'restart', 'status'}
if any(action in act_lower for action in SERVICE_ACTIONS):
    # ...
```

### Memory Usage

Each endpoint creates schema dictionaries. For large specs (>1000 endpoints), consider:

1. **Schema Reuse**: Use `$ref` to common schemas
2. **Lazy Loading**: Generate schemas on-demand
3. **Compression**: Minify JSON output

## Statistics & Metrics

### Coverage by Pattern (v25.7.6)

```python
# Calculate pattern distribution
import json
from collections import Counter

with open('src/opnsense_openapi/specs/opnsense-25.7.6.json') as f:
    spec = json.load(f)

patterns = []
for path, methods in spec['paths'].items():
    action = path.split('/')[-1].lower()

    # Categorize
    if any(x in action for x in ['start', 'stop', 'restart', 'status']):
        patterns.append('service')
    elif 'search' in action or 'find' in action:
        patterns.append('search')
    elif 'get' in action:
        patterns.append('get')
    elif any(x in action for x in ['add', 'set', 'update']):
        patterns.append('mutation')
    elif any(x in action for x in ['list', 'export']):
        patterns.append('list/export')
    else:
        patterns.append('other')

dist = Counter(patterns)
print("Pattern Distribution:")
for pattern, count in dist.most_common():
    print(f"  {pattern}: {count} ({count/len(patterns)*100:.1f}%)")
```

### Coverage Trends

Track coverage improvements over time:

```bash
# v24.7.12: 42.3% (295/697)
# v25.1.12: 67.8% (473/697)
# v25.7.6:  88.2% (615/697)
```

## Further Reading

- [Full Architecture Documentation](./ARCHITECTURE.md)
- [OPNsense MVC Documentation](https://docs.opnsense.org/development/backend.html)
- [OpenAPI Specification](https://swagger.io/specification/)
