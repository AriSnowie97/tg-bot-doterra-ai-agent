import styles from "./ChatLinkBtn.module.css";
import { LinkBtn } from "../../LinkBtn";
import { ChatSvg } from "../../../../../../../assets/icons";


const ChatLinkBtn = () => {
    return (
        <>
            <LinkBtn 
            linkTo={"/chat"}
            Svg={ChatSvg}
            h3Text={"Задати питання асистенту"}
            pText={"Відповім на основі бази знань і покажу джерела"}
            newStyles={styles}/>
        </>
    );
}

export {ChatLinkBtn};