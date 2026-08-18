import styles from "./QuestionMsg.module.css";


const QuestionMsg = ({question}) => {
    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.msgWrap}>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{question}</p>
                </div>
            </div>
        </>
    );
}

export {QuestionMsg};