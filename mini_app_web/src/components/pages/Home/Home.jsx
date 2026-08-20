import styles from "./Home.module.css";
import { useLang } from "../../../contexts/LangContext";

import { ChatLinkBtn } from "./components/LinkBtn/posterity/ChatLinkBtn";
import { ArticlesLinkBtn } from "./components/LinkBtn/posterity/ArticlesLinkBtn";
import { LinkArticleBtn } from "./components/LinkArticleBtn";
import { TelegramLinkBtn } from "./components/LinkBtn/posterity/TelegramLinkBtn";
import { articles } from "../../../dataMocks";

const Home = () => {
    const { t } = useLang();

    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.introduction}>
                    <h1>{t("home_title")}</h1>
                    <p>{t("home_subtitle")}</p>
                </div>
                <div className={styles.services}>
                    <ChatLinkBtn />
                    <ArticlesLinkBtn />
                </div>
                <div className={styles.popular}>
                    <h3>{t("popular_now")}</h3>
                    <div className={styles.articles}>
                        {articles.map((data, index) => (
                            <LinkArticleBtn
                            data={data}
                            key={index}
                            />
                        ))}
                    </div>
                </div>
                <div className={styles.links}>
                    <h3>{t("tg_channel")}</h3>
                    <div className={styles.list}>
                        <TelegramLinkBtn />
                    </div>
                </div>
                <a className={styles.contact} href="" >{t("contact_specialist")}</a>
            </div>
        </>
    );
}

export {Home};