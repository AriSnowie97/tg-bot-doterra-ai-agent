import { useRef, useEffect } from "react";

import styles from "./ReadMsgArea.module.css";
import { QuestionMsg } from "./components/QuestionMsg";
import { AnswerMsg } from "./components/AnswerMsg";


const ReadMsgArea = ({dialogueMsgs, onQuestionSubmit}) => {
    const bottomElemRef = useRef(null);

    useEffect(() => {
        bottomElemRef.current?.scrollIntoView({behavior: "smooth"});
    }, [dialogueMsgs]);

    return (
        <>
            <div className={styles.scroll}>
                <div className={styles.wrapper}>
                    {dialogueMsgs.length === 0 && (
                        <div className={styles.emptyState}>
                            <span className={styles.emptyIcon}>🌿</span>
                            <p className={styles.emptyTitle}>Привіт! Я AI-асистент dōTERRA</p>
                            <p className={styles.emptyHint}>Запитай мене про ефірні олії, БАДи або набори</p>
                            <div className={styles.suggestions}>
                                <span className={styles.chip} onClick={() => onQuestionSubmit("Яка олія від стресу?")}>Яка олія від стресу?</span>
                                <span className={styles.chip} onClick={() => onQuestionSubmit("Що таке Home Essentials Kit?")}>Що таке Home Essentials Kit?</span>
                                <span className={styles.chip} onClick={() => onQuestionSubmit("Як почати з dōTERRA?")}>Як почати з dōTERRA?</span>
                            </div>
                        </div>
                    )}

                    {dialogueMsgs.map((msg, index) =>
                        msg.isQuestion ? (
                            <QuestionMsg 
                            key={index}
                            question={msg.text}
                            />
                        ) : (
                            <AnswerMsg
                            key={index}
                            answer={msg.text}
                            />
                        )              
                    )}

                    <div ref={bottomElemRef} />
                </div>
            </div>
        </>
    );
}

export {ReadMsgArea};