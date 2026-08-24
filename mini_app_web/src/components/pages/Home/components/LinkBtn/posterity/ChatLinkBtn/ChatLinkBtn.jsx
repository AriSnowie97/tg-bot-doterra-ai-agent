import styles from "./ChatLinkBtn.module.css";
import { LinkBtn } from "../../LinkBtn";
import { ChatSvg } from "../../../../../../../assets/icons";


const ChatLinkBtn = () => {
    return (
        <>
            <LinkBtn 
            linkTo={"/chat"}
            Svg={ChatSvg}
            subject="chat"
            newStyles={styles}/>
        </>
    );
}

export {ChatLinkBtn};