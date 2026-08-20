import { useState } from "react";

import styles from "./WriteMsgArea.module.css";
import { useLang } from "../../../../../contexts/LangContext";

const WriteMsgArea = ({onQuestionSubmit}) => {
    const [question, setQuestion] = useState("");
    const { t } = useLang();

    const handleSubmit = (event) => {
        event.preventDefault();
        
        // Get question
        onQuestionSubmit(question);

        // Clearing input
        setQuestion("");
    };

    return (
        <>
            <form
            onSubmit={handleSubmit}
            method="get"
            className={styles.wrapper}
            >
                <input
                className={styles.input}
                type="text"
                name="writing"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder={t("chat_placeholder")}
                />
                <button
                className={styles.submit}
                type="submit"
                >
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                </button>
            </form>
        </>
    );
}

export {WriteMsgArea};