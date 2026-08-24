import styles from "./Contacts.module.css";
import { DotInfo } from "./components/DotInfo";
import { SimpleLink } from "./components/SimpleLink";
import { useLang } from "../../../contexts/LangContext";
import { InstagramSvg, TelegramSvg, WhatsappSvg } from "../../../assets/icons";
import specialistImg from "../../../assets/specialist.png";


const Contacts = () => {
    const { t } = useLang();


    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.about}>
                    <img className={styles.img} src={specialistImg} alt="Спеціаліст" />
                    <h2>{t("contacts_about")}</h2>
                    <p style={{whiteSpace: "pre-line"}}>
                        {t("contacts_about_description") ?? "description"}
                    </p>
                </div>
                <div className={styles.dots}>
                    <DotInfo name="IG" icon={<InstagramSvg />} href="https://www.instagram.com/nkotelianska?igsi=MTN0NHp6Z29heWRzag==" />
                    <DotInfo name="TG" icon={<TelegramSvg />} href="https://t.me/nkotelianska" />
                    {/* <DotInfo name="WA" icon={<WhatsappSvg />} href="#" /> */}
                </div>
                <div className={styles.links}>
                    <SimpleLink
                    to="/chat"
                    text={t("contacts_simple_links")?.chat?.text ?? "text"}
                    another={true}
                    />
                    <SimpleLink
                    to="/"
                    text={t("contacts_simple_links")?.specialist?.text ?? "text"}
                    />
                </div>
            </div>
        </>
    );
}

export {Contacts};