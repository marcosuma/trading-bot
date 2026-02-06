# Setup Guide

## Table of Contents

- [Setting Broker Type](#setting-broker-type)
- [Starting MongoDB](#starting-mongodb)
- [Running the System](#running-the-system)
- [Daemon Mode (Background Process)](#daemon-mode-background-process)
- [Viewing Logs](#viewing-logs)
- [Troubleshooting](#troubleshooting)

---

## Setting Broker Type

The broker type is read from the `BROKER_TYPE` environment variable. Make sure to set it **before** running the application.

### Option 1: Export in Terminal (Temporary)

```bash
export BROKER_TYPE=CTRADER
python -m live_trading.main
```

### Option 2: Create .env File (Recommended)

Create a `.env` file in the project root:

```bash
# .env file
BROKER_TYPE=CTRADER

# cTrader Configuration
CTRADER_CLIENT_ID=your_client_id
CTRADER_CLIENT_SECRET=your_client_secret
CTRADER_ACCESS_TOKEN=your_access_token
CTRADER_ENVIRONMENT=DEMO  # or LIVE

# MongoDB Configuration
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=trading_bot
```

The `.env` file will be automatically loaded by the application.

### Option 3: Set in Shell Profile (Permanent)

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
export BROKER_TYPE=CTRADER
```

Then reload:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

## Starting MongoDB

### macOS (using Homebrew)

```bash
# Install MongoDB (if not already installed)
brew tap mongodb/brew
brew install mongodb-community

# Start MongoDB
brew services start mongodb-community

# Or start manually
mongod --config /opt/homebrew/etc/mongod.conf
```

### Linux

```bash
# Start MongoDB service
sudo systemctl start mongod

# Enable auto-start on boot
sudo systemctl enable mongod

# Check status
sudo systemctl status mongod
```

### Docker

```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### MongoDB Atlas (Cloud)

If using MongoDB Atlas, set the connection string:

```bash
export MONGODB_URL="mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
```

## Verifying Configuration

After setting environment variables, verify they're loaded:

```bash
# Check broker type
echo $BROKER_TYPE

# Check MongoDB connection
mongosh mongodb://localhost:27017
```

## Troubleshooting

### Broker Type Still Shows IBKR

1. Make sure you set `BROKER_TYPE` **before** running the application
2. Check the logs - they now show both the env value and configured value
3. The value is case-insensitive (CTRADER, ctrader, Ctrader all work)
4. If using `.env` file, make sure it's in the project root directory

### MongoDB Connection Failed

1. **Check if MongoDB is running:**
   ```bash
   # macOS
   brew services list | grep mongodb

   # Linux
   sudo systemctl status mongod
   ```

2. **Check MongoDB port:**
   ```bash
   lsof -i :27017
   ```

3. **Start MongoDB if not running** (see instructions above)

4. **Check connection string:**
   - Local: `mongodb://localhost:27017`
   - Atlas: `mongodb+srv://username:password@cluster...`

### Application Crashes on Startup

The application will now show helpful error messages instead of crashing. Check the logs for:
- Broker connection issues (non-fatal - app continues)
- MongoDB connection issues (fatal - but with helpful instructions)

---

## Running the System

### Interactive Mode (Foreground)

For development or debugging, run in the foreground:

```bash
python -m live_trading.main
```

Press `Ctrl+C` to stop.

### Daemon Mode (Background Process)

For production use, run as a background daemon:

```bash
# Start the daemon
python -m live_trading.cli start

# Check if it's running
python -m live_trading.cli status

# Stop the daemon
python -m live_trading.cli stop

# Restart the daemon
python -m live_trading.cli restart
```

The daemon manager will:
- Run the process in the background
- Create a PID file (`live_trading.pid`)
- Write logs to the `logs/` directory
- Handle graceful shutdown on `stop` command

---

## Viewing Logs

### Web Interface

Navigate to `http://localhost:3000/logs` for a real-time log viewer with:
- Log level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Logger name filtering
- Full-text search
- Auto-refresh mode
- Color-coded log levels

### CLI Commands

```bash
# View recent logs
python -m live_trading.cli logs

# View last 100 logs
python -m live_trading.cli logs -n 100

# Filter by log level
python -m live_trading.cli logs -l ERROR
python -m live_trading.cli logs -l WARNING

# Search in logs
python -m live_trading.cli logs -s "ctrader"
python -m live_trading.cli logs -s "connection"

# Follow logs in real-time (like tail -f)
python -m live_trading.cli logs -f

# Output as JSON
python -m live_trading.cli logs --json
```

### Log Files

Logs are stored in the `logs/` directory:

```
logs/
├── live_trading.log          # Current log file
├── live_trading.log.1        # Rotated file
├── live_trading.log.2.gz     # Compressed older file
├── daemon_stdout.log         # Daemon stdout output
└── daemon_stderr.log         # Daemon stderr output
```

**Log Rotation:**
- Files rotate when they exceed 10 MB
- Up to 5 rotated files are kept
- Older files are automatically compressed (gzip)

### API Endpoints for Logs

| Endpoint | Description |
|----------|-------------|
| `GET /api/logs` | Retrieve logs with filters |
| `GET /api/logs/stats` | Get log file statistics |
| `GET /api/logs/errors` | Get recent errors |
| `GET /api/logs/warnings` | Get recent warnings |
| `POST /api/logs/cleanup` | Clean up old log files |
| `GET /api/daemon/status` | Get daemon process status |

**Example API Call:**

```bash
# Get last 50 ERROR logs
curl "http://localhost:8000/api/logs?level=ERROR&limit=50"

# Search for specific text
curl "http://localhost:8000/api/logs?search=ctrader&limit=100"

# Get log statistics
curl "http://localhost:8000/api/logs/stats"
```

---

## CLI Reference

### Daemon Commands

| Command | Description |
|---------|-------------|
| `python -m live_trading.cli start` | Start the daemon |
| `python -m live_trading.cli stop` | Stop the daemon |
| `python -m live_trading.cli restart` | Restart the daemon |
| `python -m live_trading.cli status` | Check daemon status |
| `python -m live_trading.cli status --json` | Status as JSON |

### Log Commands

| Command | Description |
|---------|-------------|
| `python -m live_trading.cli logs` | View recent logs |
| `python -m live_trading.cli logs -n 100` | View last 100 logs |
| `python -m live_trading.cli logs -l ERROR` | Filter by level |
| `python -m live_trading.cli logs -s "text"` | Search in logs |
| `python -m live_trading.cli logs -f` | Follow logs (tail -f) |
| `python -m live_trading.cli logs --json` | Output as JSON |
| `python -m live_trading.cli tail` | Alias for `logs -f` |
