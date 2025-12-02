const tf = require('@tensorflow/tfjs');

// Cache the trained model to avoid retraining on each prediction
let trainedModel = null;

async function trainModel() {
  try {
    const model = tf.sequential();
    // Add input layer and two dense layers for better learning
    model.add(tf.layers.dense({ units: 10, inputShape: [1], activation: 'relu' }));
    model.add(tf.layers.dense({ units: 1, activation: 'linear' }));
    model.compile({
      loss: 'meanSquaredError',
      optimizer: tf.train.adam(0.01), // Adam optimizer for faster convergence
      metrics: ['mae'], // Mean absolute error for monitoring
    });

    // Simulated Nigerian traffic data with variability (vehicles vs. predicted congestion)
    const xs = tf.tensor2d([
      [50], [60], [70], [120], [180], [100], [40], [90], [150], [200] // Diverse vehicle counts
    ]);
    const ys = tf.tensor2d([
      [60], [70], [80], [130], [190], [110], [50], [100], [160], [210] // Corresponding predictions
    ]);

    // Train with more epochs and validation split
    await model.fit(xs, ys, {
      epochs: 200,
      validationSplit: 0.2,
      callbacks: {
        onEpochEnd: async (epoch, log) => {
          if (epoch % 50 === 0) console.log(`Epoch ${epoch}: loss = ${log.loss}`);
        },
      },
    });

    return model;
  } catch (error) {
    console.error('Training failed:', error);
    throw error;
  }
}

async function predictTraffic(vehicles) {
  try {
    if (trainedModel === null) {
      trainedModel = await trainModel();
    }

    if (!Number.isFinite(vehicles) || vehicles < 0) {
      throw new Error('Invalid vehicle count: must be a non-negative number');
    }

    const input = tf.tensor2d([[vehicles]]);
    const prediction = trainedModel.predict(input).dataSync()[0];
    input.dispose(); // Clean up tensor to prevent memory leaks

    return Number(prediction.toFixed(2)); // Return rounded prediction
  } catch (error) {
    console.error('Prediction failed:', error);
    throw error;
  }
}

module.exports = { predictTraffic };