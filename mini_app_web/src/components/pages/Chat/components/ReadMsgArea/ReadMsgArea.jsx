import { useRef, useEffect } from "react";

import styles from "./ReadMsgArea.module.css";
import { QuestionMsg } from "./components/QuestionMsg";
import { AnswerMsg } from "./components/AnswerMsg";
import { useLang } from "../../../../../contexts/LangContext";


const ReadMsgArea = ({dialogueMsgs, onQuestionSubmit}) => {
    const bottomElemRef = useRef(null);
    const { t } = useLang();

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
                            <p className={styles.emptyTitle}>{t("chat_empty_title")}</p>
                            <p className={styles.emptyHint}>{t("chat_empty_hint")}</p>
                            <div className={styles.suggestions}>
                                <span className={styles.chip} onClick={() => onQuestionSubmit(t("chat_suggestion_1"))}>{t("chat_suggestion_1")}</span>
                                <span className={styles.chip} onClick={() => onQuestionSubmit(t("chat_suggestion_2"))}>{t("chat_suggestion_2")}</span>
                                <span className={styles.chip} onClick={() => onQuestionSubmit(t("chat_suggestion_3"))}>{t("chat_suggestion_3")}</span>
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