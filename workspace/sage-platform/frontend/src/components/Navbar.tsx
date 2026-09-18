import React from 'react';
import { Link } from 'react-router-dom';

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="logo">Sage AI</div>
      <div className="links">
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/whiteboard">Whiteboard</Link>
      </div>
    </nav>
  );
}
