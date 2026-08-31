import { API_URL } from "./settings";

// Getting article
const get_article = async (slug, lang, url = `${API_URL}/api/docs/`) => {
    const response = await fetch(`${url}${slug}/${lang}`);
    
    return response;
};


// Getting articles
const get_articles = async (lang, url = `${API_URL}/api/articles/`) => {
    const response = await fetch(`${url}${lang}`);
    
    return response;
};


export {get_article, get_articles};