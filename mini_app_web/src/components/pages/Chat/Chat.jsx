import styles from "./Chat.module.css";
import { ReadMsgArea } from "./components/ReadMsgArea";
import { WriteMsgArea } from "./components/WriteMsgArea";

const Chat = () => {
    return (
        <>
            <div className={styles.wrapper}>
                <ReadMsgArea />
                <WriteMsgArea />
            </div>
        </>
    );
}

export {Chat};