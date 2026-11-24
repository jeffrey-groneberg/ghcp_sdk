# 10 · Identity

Deck slide 24 · [Source](10_identity.py) · [Multi-tenancy](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/setup/multi-tenancy.md) · [Authentication](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/auth/authenticate.md)

The pattern for a service with many users: each session runs as its user,
with only the tools you allow.

## Run it

```bash
python examples/10_identity.py
```

## How it works

```python
client = CopilotClient(
    mode="empty",                                  # no ambient host tools
    runtime=RuntimeConnection.for_default(base_directory=TENANT_HOME),
    github={"use_logged_in_user": False})
...
session = await client.create_session(
    github={"token": user_token()},                # runs as this user only
    tools={"definitions": [get_failed_tests],
           "available_tools": ["custom:*"]},       # explicit allow-list
    ...)
```

- `mode="empty"` turns off the host's shell, files and default tools, as well
  as skills, custom instructions and telemetry. Every session must list its
  tools, and the client needs storage you name: `base_directory`, `session_fs`
  (example 14) or a runtime server (example 11).
- `github={"use_logged_in_user": False}` gives the runtime no identity of its own.
- `github={"token": ...}` makes the session run as one user, so its model
  calls count against that user's Copilot plan. In production, pass
  `github={"token_provider": ...}` so short-lived tokens are renewed. Here,
  `gh auth token` stands in for the signed-in user's token.
- `["custom:*"]` admits only your own tools, so when the model reaches for
  `bash`, the runtime answers that the tool doesn't exist.
- The `GitHubAuthApi` group (`session.rpc.git_hub_auth`) and its
  `SessionAuthStatus` result are experimental in SDK 2.0.1.

## Output from a live run

```text
runtime signed in: False · session signed in: True (token)
[tool refused] Tool 'bash' does not exist.
Build 4711 failed because `test_login` hit a `TimeoutError`: the auth service timed out after 30 s. I couldn't list the current directory because the bash tool isn't available in this session.
```
