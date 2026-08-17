import styles from "./ChatLinkBtn.module.css";
import { LinkBtn } from "../../LinkBtn";

const ChatLinkBtn = () => {
    return (
        <>
            <LinkBtn 
            linkTo={"/chat"}
            img={""}
            h3Text={"Задати питання асистенту"}
            pText={"Відповім на основі бази знань і покажу джерела"}
            newStyles={styles}/>
        </>
    );
}

export {ChatLinkBtn};