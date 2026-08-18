import { useRef, useEffect } from "react";

import styles from "./ReadMsgArea.module.css";
import { QuestionMsg } from "./components/QuestionMsg";
import { AnswerMsg } from "./components/AnswerMsg";


const ReadMsgArea = ({dialogueMsgs}) => {
    const bottomElemRef = useRef(null);

    useEffect(() => {
        bottomElemRef.current?.scrollIntoView({behavior: "smooth"});
    }, [dialogueMsgs]);

    return (
        <>
            <div className={styles.scroll}>
                <div className={styles.wrapper}>
                    {dialogueMsgs.map((msg, index) =>
                        msg.isQuestion ? (
                            <QuestionMsg 
                            key={index}
                            question={msg.text}
                            />
                            // <p>Hello</p>
                        ) : (
                            <AnswerMsg
                            key={index}
                            answer={msg.text}
                            />
                            // <p>bye</p>
                        )              
                    )}

                    <div ref={bottomElemRef} />
                </div>
            </div>
        </>
    );
}

export {ReadMsgArea};