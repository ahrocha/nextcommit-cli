# nextcommit-cli

Standalone CLI (single Python file) that:

1. Fetches daily heartbeats from WakaTime.
2. Sends the payload to OpenAI.
3. Prints raw payload responses.
4. Prints final recommendations.

## Requirements

- Python 3.9+ (standard library only).
- A WakaTime API token.
- An OpenAI API token.

## Where to get tokens

- WakaTime token (API Key): https://wakatime.com/api-key
- OpenAI token (API Keys page): https://platform.openai.com/api-keys

## Pricing notice

Both services may charge you depending on your plan and usage:

- WakaTime can have paid plans/features.
- OpenAI API usage is billed based on token consumption and model pricing.

Always verify current pricing directly on each service website before running the CLI.

## Usage

From the repository root:

```bash
python3 nextcommit-cli/nextcommit_cli.py <wakatime_token> <openai_token> [date]
```

Arguments:

- wakatime_token (required)
- openai_token (required)
- date (optional, format: YYYY-MM-DD, default: yesterday)

## Example

```bash
python3 nextcommit-cli/nextcommit_cli.py wk_xxxxxxxxxxxxxxxxxxxxx sk-proj-xxxxxxxxxxxxxxxxxxxxx 2026-03-13
```

## Output behavior

The CLI prints, in order:

1. Raw WakaTime payload.
2. Raw OpenAI payload.
3. Final recommendations text.

## Notes

- The date must be in the past.
- If no date is provided, the CLI uses yesterday.
- This CLI is designed for a single user per execution.
