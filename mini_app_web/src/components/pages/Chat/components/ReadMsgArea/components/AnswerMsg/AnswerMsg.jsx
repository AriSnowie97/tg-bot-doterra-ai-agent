import styles from "./AnswerMsg.module.css";


const AnswerMsg = ({answer}) => {
    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.msgWrap}>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{answer}</p>
                </div>
            </div>
        </>
    );
}

export {AnswerMsg};