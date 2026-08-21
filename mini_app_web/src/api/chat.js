import { API_URL } from "./settings";

// Getting chat answer for question
const post_chat_question = async (question, url = `${API_URL}/api/chat`) => {
    const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: question })
            });

    return response;
};


export {post_chat_question};