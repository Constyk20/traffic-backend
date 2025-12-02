const mongoose = require('mongoose');

const TrafficSchema = new mongoose.Schema({
  location: { type: String, required: true },
  vehicles: { type: Number, required: true },
  timestamp: { type: Date, default: Date.now },
});

module.exports = mongoose.model('Traffic', TrafficSchema);