import styles from "./TelegramLinkBtn.module.css";
import { LinkBtn } from "../../LinkBtn";
import { TelegramSvg } from "../../../../../../../assets/icons";


const TelegramLinkBtn = () => {
    return (
        <>
            <LinkBtn 
            linkTo={"https://t.me/doterra_ua_assistant_bot"}
            Svg={TelegramSvg}
            subject="telegram"
            newStyles={styles}/>
        </>
    );
}

export {TelegramLinkBtn};