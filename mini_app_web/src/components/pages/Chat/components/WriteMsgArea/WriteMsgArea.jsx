import { useState } from "react";

import styles from "./WriteMsgArea.module.css";


const WriteMsgArea = () => {
    const [question, setQuestion] = useState("")

    const handleSubmit = (event) => {
        event.preventDefault();


        // Clearing input
        setQuestion("");
    };

    return (
        <>
            <form
            onSubmit={handleSubmit}
            method="get"
            className={styles.wrapper}>
                <input
                className={styles.input}
                type="text"
                name="question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Введіть запитання"
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