const express = require('express');
const app = express();
const port = 3000;

app.get('/data', (req, res) => {
    const size = parseInt(req.query.size) || 1; // size in KB
    const data = 'x'.repeat(size * 1024);
    res.json({
        service: 'service-c',
        payload_size_kb: size,
        data: data
    });
});

app.get('/health', (req, res) => res.send('OK'));

app.listen(port, () => console.log(`Service C listening on port ${port}`));
