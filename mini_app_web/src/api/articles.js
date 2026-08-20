import { API_URL } from "./settings";

// Getting article
const get_article = async (slug, url = `${API_URL}/api/docs/`) => {
    const response = await fetch(`${url}${slug}`);
    
    return response;
};


// Getting articles
const get_articles = async (url = `${API_URL}/api/articles`) => {
    const response = await fetch(`${url}`);
    
    return response;
};


export {get_article, get_articles};