const express = require('express');
const axios = require('axios');
const app = express();
const port = 3000;

const SERVICE_C_URL = process.env.SERVICE_C_URL || 'http://service-c:3000';

app.get('/process', async (req, res) => {
    try {
        const response = await axios.get(`${SERVICE_C_URL}/data`, {
            params: req.query
        });
        res.json({
            service: 'service-b',
            data: response.data
        });
    } catch (error) {
        res.status(500).json({ error: error.message, target: SERVICE_C_URL });
    }
});

app.get('/health', (req, res) => res.send('OK'));

app.listen(port, () => console.log(`Service B listening on port ${port}`));
