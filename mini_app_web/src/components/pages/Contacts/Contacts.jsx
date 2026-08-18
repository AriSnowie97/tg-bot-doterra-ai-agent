import styles from "./Contacts.module.css";
import { DotInfo } from "./components/DotInfo";
import { SimpleLink } from "./components/SimpleLink";


const Contacts = () => {
    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.about}>
                    <div className={styles.img}>Image</div>
                    <h2>Про спеціаліста</h2>
                    <p>
                        Сертифікований нутриціолог і консультант з догляду за шкірою.Відповідаю на питання про БАД, косметологічні пристрої та щоденні ритуали догляду.
                    </p>
                </div>
                <div className={styles.dots}>
                    <DotInfo name="IG" />
                    <DotInfo name="TG" />
                    <DotInfo name="WA" />
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