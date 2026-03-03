const express = require('express');
const axios = require('axios');
const app = express();
const port = 3000;

const SERVICE_B_URL = process.env.SERVICE_B_URL || 'http://service-b:3000';

app.get('/test', async (req, res) => {
    const start = Date.now();
    try {
        const response = await axios.get(`${SERVICE_B_URL}/process`, {
            params: req.query
        });
        const duration = Date.now() - start;
        res.json({
            service: 'service-a',
            chain_duration_ms: duration,
            backend_response: response.data
        });
    } catch (error) {
        res.status(500).json({ error: error.message, target: SERVICE_B_URL });
    }
});

app.get('/health', (req, res) => res.send('OK'));

app.listen(port, () => console.log(`Service A listening on port ${port}`));
