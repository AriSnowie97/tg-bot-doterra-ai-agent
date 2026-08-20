import { useState } from "react";

import styles from "./WriteMsgArea.module.css";
import { useLang } from "../../../../../contexts/LangContext";
import { SendMsgSvg } from "../../../../../assets/icons";

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
                    <SendMsgSvg />
                </button>
            </form>
        </>
    );
}

export {WriteMsgArea};