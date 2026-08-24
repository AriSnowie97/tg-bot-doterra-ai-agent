import styles from "./Contacts.module.css";
import { DotInfo } from "./components/DotInfo";
import { SimpleLink } from "./components/SimpleLink";
import { useLang } from "../../../contexts/LangContext";


const Contacts = () => {
    const { t } = useLang();


    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.about}>
                    <div className={styles.img}>Image</div>
                    <h2>{t("contacts_about")}</h2>
                    <p>{t("contacts_about_description")}</p>
                </div>
                <div className={styles.dots}>
                    <DotInfo name="IG" />
                    <DotInfo name="TG" />
                    <DotInfo name="WA" />
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