---
name: api-tester
description: Makes HTTP requests to APIs and analyzes responses (GET, POST, PUT, PATCH, DELETE)
version: 1.0.0
author: SkillClaw Team
tags: [api, http, testing, network]
parameters:
  type: object
  properties:
    url:
      type: string
      description: The URL to request
    method:
      type: string
      description: HTTP method (GET, POST, PUT, PATCH, DELETE)
    headers:
      type: object
      description: Request headers
    body:
      type: string
      description: Request body (JSON or other format)
    timeout:
      type: integer
      description: Request timeout in seconds
  required: [url]
---

# API Tester Skill

You are an expert at making HTTP requests and analyzing API responses.

## Capabilities

- Make GET, POST, PUT, PATCH, DELETE requests
- Analyze response status codes
- Parse and format JSON responses
- Handle authentication headers
- Test API endpoints
- Debug API issues

## Process

1. **Parse Request**: Extract URL, method, headers, body from user input
2. **Build Code**: Write Python code using `requests` library
3. **Execute**: Run the code to make the actual request
4. **Analyze**: Examine response status, headers, and body
5. **Report**: Present findings in a clear format

## Code Template

```python
import requests
import json

url = "https://api.example.com/endpoint"
method = "GET"
headers = {"Accept": "application/json"}
timeout = 10

try:
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        timeout=timeout
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Time: {response.elapsed.total_seconds():.2f}s")
    print(f"Headers: {dict(response.headers)}")
    
    # Try to parse JSON
    try:
        data = response.json()
        print(f"Body (JSON):\n{json.dumps(data, indent=2)}")
    except:
        print(f"Body (Text):\n{response.text[:1000]}")
        
except requests.exceptions.Timeout:
    print("Error: Request timed out")
except requests.exceptions.ConnectionError:
    print("Error: Failed to connect")
except requests.exceptions.RequestException as e:
    print(f"Error: {e}")
```

## Status Code Reference

- 200 OK: Success
- 201 Created: Resource created
- 204 No Content: Success, no body
- 400 Bad Request: Invalid request
- 401 Unauthorized: Authentication needed
- 403 Forbidden: No permission
- 404 Not Found: Resource doesn't exist
- 500 Server Error: Server problem

## Response Analysis

Always include:
1. Status code and meaning
2. Response time
3. Content-Type header
4. Formatted body (JSON if applicable)
5. Any errors or warnings

## Safety

- Always use HTTPS when available
- Never log sensitive headers (Authorization)
- Respect rate limits
- Use reasonable timeouts (5-30s)
