# cTrader Token Generator Script

This script helps you obtain an access token for the cTrader Open API.

## Prerequisites

1. **Register your application** at https://id.ctrader.com/apps
   - You'll get a `Client ID` and `Client Secret`
   - Set a `Redirect URI` (e.g., `http://localhost:8000/callback`)

2. **Set environment variables**:
   ```bash
   export CTRADER_CLIENT_ID="your_client_id"
   export CTRADER_CLIENT_SECRET="your_client_secret"
   export CTRADER_REDIRECT_URI="http://localhost:8000/callback"  # Optional, defaults to http://localhost:8000/callback
   ```

## Usage

### Interactive Mode (Recommended)

The script will start a local server to automatically receive the authorization code:

```bash
python live_trading/scripts/get_ctrader_token.py --interactive
```

Or simply:
```bash
python live_trading/scripts/get_ctrader_token.py
```

Then choose option 1 when prompted.

### Manual Mode

If you prefer to manually copy the authorization code:

```bash
python live_trading/scripts/get_ctrader_token.py --manual
```

## What the Script Does

1. **Generates Authorization URL**: Creates the URL you need to visit to authorize your application
2. **Receives Authorization Code**: Either automatically via local server (interactive) or manually (you paste it)
3. **Exchanges Code for Token**: Converts the authorization code into an access token
4. **Saves Token**: Optionally saves the token to your `.env` file

## Example Output

```
======================================================================
cTrader Open API - Access Token Generator
======================================================================

Client ID: 1234567890...abcd
Redirect URI: http://localhost:8000/callback

Starting callback server on http://localhost:8000/callback
Waiting for authorization...

Please open this URL in your browser:

https://id.ctrader.com/my/settings/openapi/grantingaccess/?client_id=...

After authorizing, the script will automatically receive the code.
Waiting for callback... (Press Ctrl+C to cancel)
✓ Authorization code received!

Exchanging authorization code for access token...

======================================================================
SUCCESS! Access Token obtained
======================================================================

Access Token: abc123xyz...

Add this to your environment variables:
  export CTRADER_ACCESS_TOKEN='abc123xyz...'

Or add it to your .env file:
  CTRADER_ACCESS_TOKEN=abc123xyz...
```

## Troubleshooting

- **"Client ID not found"**: Make sure you've set `CTRADER_CLIENT_ID` environment variable
- **"Authorization failed"**: Check that your redirect URI matches exactly what you registered
- **"Port already in use"**: Use `--port` to specify a different port, or update your redirect URI
- **"Timeout waiting for code"**: Make sure you've authorized the application in your browser

## Security Notes

- Never commit your `CLIENT_SECRET` or `ACCESS_TOKEN` to version control
- Store credentials in environment variables or a secure secrets manager
- The access token may expire - you'll need to regenerate it if it does

