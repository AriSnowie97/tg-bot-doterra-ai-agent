import { API_URL } from "./settings";

// Getting chat answer for question
// initData підписаний Telegram — бекенд перевіряє ним, що запит прийшов із Mini App
const post_chat_question = async (question, url = `${API_URL}/api/chat`) => {
    const initData = window.Telegram?.WebApp?.initData || "";
    const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': initData,
                },
                body: JSON.stringify({ query: question })
            });

    return response;
};


export {post_chat_question};