import { useState } from "react";

import styles from "./Chat.module.css";
import { ReadMsgArea } from "./components/ReadMsgArea";
import { WriteMsgArea } from "./components/WriteMsgArea";


const Chat = () => {
    const [dialogueMsgs, setDialogueMsgs] = useState([])

    const onQuestionSubmit = (question) => {
        setDialogueMsgs(prev => [
            ...prev,
            {
                isQuestion: true,
                text: question
            }
        ]);

        //!
        // setDialogueMsgs(prev => [
        //     ...prev,
        //     {
        //         isQuestion: false,
        //         text: answer
        //     }
        // ]);
    };

    return (
        <>
            <div className={styles.wrapper}>
                <ReadMsgArea
                    dialogueMsgs={dialogueMsgs}
                />
                <WriteMsgArea
                    onQuestionSubmit={onQuestionSubmit}
                />
            </div>
        </>
    );
}

export {Chat};