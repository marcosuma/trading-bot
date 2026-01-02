# Frontend Troubleshooting

Common issues and solutions for the Live Trading System frontend.

See [Frontend Guide](frontend.md) for setup and [Live Trading System](README.md) for overview.

## "Cannot GET /" Error

This error typically means:

1. **Dev server is not running**: Make sure you've started the dev server with `npm run dev`
2. **Wrong port**: Check the terminal output to see which port Vite is actually using
3. **Port conflict**: If port 3000 is taken, Vite will automatically use the next available port (3001, 3002, etc.)

## Steps to Fix

1. **Stop any running dev server** (Ctrl+C)

2. **Make sure you're in the frontend directory**:
   ```bash
   cd live_trading/frontend
   ```

3. **Install/update dependencies**:
   ```bash
   npm install
   ```

4. **Start the dev server**:
   ```bash
   npm run dev
   ```

5. **Check the terminal output** - it should show something like:
   ```
   VITE v4.x.x  ready in xxx ms

   ➜  Local:   http://localhost:3000/
   ➜  Network: use --host to expose
   ```

6. **Access the URL shown in the terminal** (usually `http://localhost:3000`)

## Common Issues

### Port Already in Use
If you see "Port 3000 is in use, trying another one...", Vite will use a different port. Check the terminal to see which port it's using.

### Node.js Version
Make sure you're using Node.js 18+ (or Node.js 16 with Vite 4.x). Check with:
```bash
node --version
```

### Dependencies Not Installed
If you see module errors, reinstall dependencies:
```bash
rm -rf node_modules package-lock.json
npm install
```

### Browser Console Errors
Open browser developer tools (F12) and check the Console tab for any JavaScript errors.

