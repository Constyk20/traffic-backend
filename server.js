const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const connectDB = require('./config/db');
const trafficRoutes = require('./routes/trafficRoutes');
const { predictTraffic } = require('./ml/trafficModel');
require('dotenv').config();

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: '*' }, // Allow Flutter app to connect
});

// Middleware
app.use(cors());
// Enhanced JSON parsing with debugging
app.use((req, res, next) => {
  express.json({ limit: '10kb', strict: false })(req, res, (err) => {
    if (err) {
      console.error('JSON parsing error:', err.message, 'Raw body:', req.body);
      return res.status(400).json({ error: 'Invalid JSON format', details: err.message });
    }
    next();
  });
});

// Connect to MongoDB with error handling
const connectWithRetry = () => {
  connectDB().catch(err => {
    console.error('MongoDB connection error:', err);
    setTimeout(connectWithRetry, 5000); // Retry every 5 seconds
  });
};
connectWithRetry();

// Store io instance for routes to use
app.set('io', io);

// Routes
app.use('/api', trafficRoutes);

// Remove duplicate /api/traffic-data route to rely on trafficRoutes
// Socket.IO event handlers
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);

  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
  });
});

// Start server with error handling
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
}).on('error', (err) => {
  console.error('Server error:', err);
});