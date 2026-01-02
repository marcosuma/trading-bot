# Live Trading System - Frontend

React-based frontend for the Live Trading System.

See [Live Trading System](README.md) for overview and setup instructions.

## Features

- **Dashboard**: Overview of all operations and overall statistics
- **Operations Management**: List, view, create, pause, resume, and stop operations
- **Operation Details**: Detailed view with positions, transactions, trades, and orders
- **Real-time Updates**: Auto-refreshes data every 5 seconds
- **Responsive Design**: Clean and modern UI

## Setup

### Prerequisites

- Node.js 18+ and npm (Node.js 16 may work but 18+ is recommended)

### Installation

1. Install dependencies:
```bash
npm install
```

2. Configure API URL (optional):
Create a `.env` file:
```env
VITE_API_URL=http://localhost:8000
```

3. Start development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

**Note**: Make sure you're accessing `http://localhost:3000` (not 3001). If port 3000 is already in use, Vite will automatically use the next available port (e.g., 3001). Check the terminal output to see which port Vite is actually using.

## Build for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Project Structure

```
src/
├── api/
│   └── client.js          # API client with axios
├── pages/
│   ├── Dashboard.jsx      # Main dashboard
│   ├── Operations.jsx      # Operations list
│   ├── CreateOperation.jsx # Create operation form
│   └── OperationDetail.jsx # Operation details view
├── utils/
│   └── formatters.js      # Utility functions for formatting
├── App.jsx                 # Main app component with routing
├── App.css                 # App styles
├── main.jsx                # Entry point
└── index.css               # Global styles
```

## API Integration

The frontend communicates with the FastAPI backend through the API client in `src/api/client.js`. All API calls are centralized there.

## Features in Detail

### Dashboard
- Overall statistics (total operations, active operations, total trades, P/L)
- Recent active operations list
- Quick access to create new operations

### Operations List
- Filter by status (active, paused, closed)
- View all operations with key metrics
- Actions: View, Pause, Resume, Stop

### Create Operation
- Form to create new trading operations
- Configure asset, bar sizes, strategy
- Risk management settings (stop loss, take profit)
- Crash recovery configuration

### Operation Detail
- Tabbed interface with:
  - **Overview**: Operation details and statistics
  - **Positions**: Open and closed positions
  - **Transactions**: All buy/sell transactions
  - **Trades**: Completed round-trip trades
  - **Orders**: All placed orders

## Development

The frontend uses:
- **React 18** with hooks
- **React Router** for navigation
- **Axios** for API calls
- **Vite** as build tool
- Plain CSS for styling (no CSS framework)

## Future Enhancements

- WebSocket integration for real-time updates
- Charts for P/L visualization
- Strategy performance graphs
- Position charts
- Alerts and notifications

