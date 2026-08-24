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
                    <h2>Про спеціаліста</h2>
                    <p>
                        Ефірні олії | Аромапрактик | Нутриціолог | Київ<br />
                        Аромаексперт тіла й душі<br />
                        Ефірні олії, замість аптечки<br />
                        Консультую,<br />
                        коли аналізи в нормі, а самопочуття ні<br />
                        Підбір ефірних олій та БАД 👇🏼
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