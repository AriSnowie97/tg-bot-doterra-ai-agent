import styles from "./TelegramLinkBtn.module.css";
import { LinkBtn } from "../../LinkBtn";

const TelegramLinkBtn = () => {
    return (
        <>
            <LinkBtn 
            linkTo={"/telegram"}
            img={""}
            h3Text={"Наш телеграм"}
            pText={"Посилання на телеграм-бота"}
            newStyles={styles}/>
        </>
    );
}

export {TelegramLinkBtn};