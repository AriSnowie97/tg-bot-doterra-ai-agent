import styles from "./Contacts.module.css";
import { DotInfo } from "./components/DotInfo";
import { SimpleLink } from "./components/SimpleLink";
import { InstagramSvg, TelegramSvg, WhatsappSvg } from "../../../assets/icons";


const Contacts = () => {
    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.about}>
                    <img className={styles.img} src="/specialist.png" alt="Спеціаліст" />
                    <h2>Про спеціаліста</h2>
                    <p>
                        Сертифікований нутриціолог і консультант з догляду за шкірою.Відповідаю на питання про БАД, косметологічні пристрої та щоденні ритуали догляду.
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
                    text="Написати асистенту в чаті"
                    another={true}
                    />
                    <SimpleLink
                    to="/"
                    text="Написати спеціалісту напряму"
                    />
                </div>
            </div>
        </>
    );
}

export {Contacts};