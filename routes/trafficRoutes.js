const express = require('express');
const router = express.Router();
const Traffic = require('../models/traffic');
const { predictTraffic } = require('../ml/trafficModel');

router.post('/traffic-data', async (req, res) => {
  try {
    const { location, vehicles } = req.body;
    if (!location || !Number.isFinite(vehicles) || vehicles < 0) {
      return res.status(400).json({ error: 'Invalid location or vehicle count' });
    }
    const trafficData = new Traffic({ location, vehicles, timestamp: new Date() });
    await trafficData.save();
    const prediction = await predictTraffic(vehicles);
    const responseData = { ...trafficData.toObject(), prediction };
    req.app.get('io').emit('prediction', responseData);
    res.status(201).json(responseData);
  } catch (error) {
    console.error('Traffic data error:', error);
    res.status(500).json({ error: 'Failed to process traffic data', details: error.message });
  }
});

router.get('/traffic-data', async (req, res) => {
  try {
    const { location, limit = 10 } = req.query;
    let query = Traffic.find().sort({ timestamp: -1 }).limit(Number(limit));
    if (location) query = query.where('location').equals(location);
    const data = await query.exec();
    if (!data.length) return res.status(404).json({ error: 'No traffic data found' });
    res.json(data);
  } catch (error) {
    console.error('Traffic data retrieval error:', error);
    res.status(500).json({ error: 'Failed to retrieve traffic data', details: error.message });
  }
});

module.exports = router;