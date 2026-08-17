import styles from "./ReadMsgArea.module.css";

const ReadMsgArea = () => {
    return (
        <>
            <div className={styles.scroll}>
                <div className={styles.wrapper}>
                    <div className={styles.ab}></div>
                    Hello 3
                    <div className={styles.ab}></div>
                    Hello 2
                    <div className={styles.ab}></div>
                    Hello 1

                </div>
            </div>
        </>
    );
}

export {ReadMsgArea};