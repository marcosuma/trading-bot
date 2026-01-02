import React from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Operations from './pages/Operations'
import OperationDetail from './pages/OperationDetail'
import CreateOperation from './pages/CreateOperation'
import './App.css'

function App() {
  return (
    <Router>
      <div className="app">
        <nav className="navbar">
          <div className="container">
            <div className="nav-content">
              <Link to="/" className="nav-logo">
                Live Trading System
              </Link>
              <div className="nav-links">
                <Link to="/">Dashboard</Link>
                <Link to="/operations">Operations</Link>
                <Link to="/operations/create">Create Operation</Link>
              </div>
            </div>
          </div>
        </nav>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/operations" element={<Operations />} />
            <Route path="/operations/create" element={<CreateOperation />} />
            <Route path="/operations/:id" element={<OperationDetail />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App

