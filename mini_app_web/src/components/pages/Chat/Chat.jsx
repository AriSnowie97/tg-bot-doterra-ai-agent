import { useState, useEffect } from "react";

import styles from "./Chat.module.css";
import { ReadMsgArea } from "./components/ReadMsgArea";
import { WriteMsgArea } from "./components/WriteMsgArea";
import { useLang } from "../../contexts/LangContext";


const Chat = () => {
    const { t } = useLang();
    const [dialogueMsgs, setDialogueMsgs] = useState(() => {
        const saved = localStorage.getItem("chat_history");
        return saved ? JSON.parse(saved) : [];
    });

    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        localStorage.setItem("chat_history", JSON.stringify(dialogueMsgs));
    }, [dialogueMsgs]);

    const onQuestionSubmit = async (question) => {
        if (!question.trim() || isLoading) return;

        setDialogueMsgs(prev => [
            ...prev,
            { isQuestion: true, text: question }
        ]);
        
        setIsLoading(true);
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) typingIndicator.style.display = 'block';

        try {
            const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_URL}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: question })
            });
            
            if (!response.ok) throw new Error('API Error');
            
            const data = await response.json();
            
            setDialogueMsgs(prev => [
                ...prev,
                { isQuestion: false, text: data.response }
            ]);
        } catch (error) {
            console.error(error);
            setDialogueMsgs(prev => [
                ...prev,
                { isQuestion: false, text: t("chat_error") }
            ]);
        } finally {
            setIsLoading(false);
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) typingIndicator.style.display = 'none';
        }
    };

    return (
        <>
            <div className={styles.wrapper}>
                <ReadMsgArea
                    dialogueMsgs={dialogueMsgs}
                    onQuestionSubmit={onQuestionSubmit}
                />
                <WriteMsgArea
                    onQuestionSubmit={onQuestionSubmit}
                />
            </div>
        </>
    );
}

export {Chat};