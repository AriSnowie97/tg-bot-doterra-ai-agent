import { useState } from "react";

import styles from "./Chat.module.css";
import { ReadMsgArea } from "./components/ReadMsgArea";
import { WriteMsgArea } from "./components/WriteMsgArea";


const Chat = () => {
    const [dialogueMsgs, setDialogueMsgs] = useState([])

    const onQuestionSubmit = (question) => {
        if (!question.trim()) return;

        setDialogueMsgs(prev => [
            ...prev,
            {
                isQuestion: true,
                text: question
            }
        ]);

        // Simulate bot typing and answering
        setTimeout(() => {
            setDialogueMsgs(prev => [
                ...prev,
                {
                    isQuestion: false,
                    text: "Привіт! Я AI-асистент doTERRA. Наразі чат в Mini App працює в демо-режимі. Щоб отримати справжню відповідь від бази знань, будь ласка, закрийте це вікно і напишіть своє запитання безпосередньо в чат зі мною!"
                }
            ]);
        }, 1000);
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