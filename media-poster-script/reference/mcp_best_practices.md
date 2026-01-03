# MCP Best Practices

This document provides guidelines for designing and implementing MCP tools that work well with LLM agents.

## Tool Naming Conventions

Use clear, descriptive names with consistent prefixes:

```
# Good examples
github_create_issue
github_list_repos
github_get_pull_request

# Avoid
create_issue
list_repos
get_pr
```

**Rules:**
- Use lowercase with underscores (snake_case)
- Include the service/namespace prefix
- Use action verbs: create, list, get, update, delete
- Be specific: `get_user_by_id` not `get_user`

## Response Format Guidelines

### JSON Responses (Recommended)

Return structured JSON when possible:

```json
{
  "success": true,
  "data": {...},
  "metadata": {
    "page": 1,
    "per_page": 10,
    "total": 100
  }
}
```

### Markdown Responses

For text-heavy outputs, use markdown formatting:

```markdown
# Results

## Item 1
- **Name**: Example
- **Status**: Active

## Item 2
- **Name**: Another
- **Status**: Inactive
```

## Pagination

Implement consistent pagination across list operations:

```python
def list_items(page: int = 1, per_page: int = 20) -> dict:
    """List items with pagination support."""
    offset = (page - 1) * per_page
    items = db.query(limit=per_page, offset=offset)
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total_count
    }
```

**Parameters:**
- `page`: 1-based page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)

## Error Handling

Provide actionable error messages:

```python
# Bad
raise Exception("Failed")

# Good
raise ValueError(
    "Invalid input: 'status' must be one of "
    "['active', 'inactive', 'pending']. "
    f"Got: '{invalid_value}'"
)
```

**Error types:**
- `ValueError` - Invalid input parameters
- `PermissionError` - Authentication/authorization failures
- `NotFoundError` - Resource not found
- `RateLimitError` - Too many requests

## Transport Selection

### Use stdio when:
- Server runs locally
- Simple process management needed
- No network access required

### Use HTTP/SSE when:
- Server is remote
- Multiple clients need access
- Scalability is important

## Security Considerations

1. **Never log secrets** in tool responses
2. **Validate all inputs** before processing
3. **Use least privilege** for API credentials
4. **Sanitize outputs** to prevent information leakage

## Tool Annotations

Mark tools with appropriate hints:

```python
@mcp.tool(
    readOnlyHint=True,        # Does not modify state
    destructiveHint=False,    # No side effects
    idempotentHint=True,      # Same input = same output
    openWorldHint=False,      # No external network calls
)
def create_resource(data: dict) -> dict:
    """Create a new resource."""
    ...
```
