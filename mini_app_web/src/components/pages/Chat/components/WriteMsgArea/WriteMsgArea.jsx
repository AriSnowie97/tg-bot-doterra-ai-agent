import { useState } from "react";

import styles from "./WriteMsgArea.module.css";


const WriteMsgArea = ({onQuestionSubmit}) => {
    const [question, setQuestion] = useState("");
    // const [writing, setWriting] = useState("");

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
                placeholder="Введіть запитання..."
                />
                <input
                className={styles.submit}
                type="submit"
                value="-->"
                />
            </form>
        </>
    );
}

export {WriteMsgArea};