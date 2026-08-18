import { useState } from "react";

import styles from "./Chat.module.css";
import { ReadMsgArea } from "./components/ReadMsgArea";
import { WriteMsgArea } from "./components/WriteMsgArea";


const Chat = () => {
    const [dialogueMsgs, setDialogueMsgs] = useState([])

    const [isLoading, setIsLoading] = useState(false);

    const onQuestionSubmit = async (question) => {
        if (!question.trim() || isLoading) return;

        setDialogueMsgs(prev => [
            ...prev,
            { isQuestion: true, text: question }
        ]);
        
        setIsLoading(true);

        try {
            const API_URL = import.meta.env.VITE_API_URL || '';
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
                { isQuestion: false, text: "Вибачте, виникла помилка при зв'язку з бекендом. Переконайтесь, що app.py запущено!" }
            ]);
        } finally {
            setIsLoading(false);
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