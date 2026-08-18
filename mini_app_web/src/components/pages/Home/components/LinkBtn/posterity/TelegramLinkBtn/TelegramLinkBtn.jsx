import styles from "./TelegramLinkBtn.module.css";
import { LinkBtn } from "../../LinkBtn";
import { TelegramSvg } from "../../../../../../../assets/images";


const TelegramLinkBtn = () => {
    return (
        <>
            <LinkBtn 
            linkTo={"https://t.me/doterra_ua_assistant_bot"}
            Svg={TelegramSvg}
            h3Text={"Наш телеграм"}
            pText={"Посилання на телеграм-бота"}
            newStyles={styles}/>
        </>
    );
}

export {TelegramLinkBtn};