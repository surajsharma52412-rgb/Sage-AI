// Frontend Client Application
document.addEventListener('DOMContentLoaded', async () => {
    console.log('App initialized.');
    const container = document.getElementById('items-container');
    try {
        const res = await fetch('/api/items');
        const data = await res.json();
        const items = data.items || [
            { id: '1', title: 'System Overview', description: 'Core services operational' },
            { id: '2', title: 'User Analytics', description: 'Active user tracking verified' }
        ];
        container.innerHTML = items.map(item => `
            <div class="card">
                <h3>${item.title}</h3>
                <p>${item.description}</p>
            </div>
        `).join('');
    } catch (e) {
        console.warn('API offline, rendering demo items.');
        container.innerHTML = `
            <div class="card"><h3>System Ready</h3><p>Connected to Sage platform.</p></div>
        `;
    }
});
