const resolveApiUrl = () => {
    if (import.meta.env.VITE_API_URL) {
        return import.meta.env.VITE_API_URL;
    }
    if (typeof window !== 'undefined') {
        const host = window.location.hostname;
        if (host === 'localhost' || host === '127.0.0.1') {
            return 'http://localhost:8000';
        }
        if (host.endsWith('railway.app')) {
            return window.location.origin;
        }
    }
    return 'https://tg-bot-doterra-ai-agent-production.up.railway.app';
};

const API_URL = resolveApiUrl();

export {API_URL};