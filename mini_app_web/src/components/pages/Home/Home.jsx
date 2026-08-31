import { useEffect, useState } from "react";

import styles from "./Home.module.css";
import { useLang } from "../../../contexts/LangContext";
import { ChatLinkBtn } from "./components/LinkBtn/posterity/ChatLinkBtn";
import { ArticlesLinkBtn } from "./components/LinkBtn/posterity/ArticlesLinkBtn";
import { LinkArticleBtn } from "./components/LinkArticleBtn";
import { TelegramLinkBtn } from "./components/LinkBtn/posterity/TelegramLinkBtn";
import { get_articles } from "../../../api/articles";


const Home = () => {
    const [articlesList, setArticlesList] = useState([]);
    const [loading, setLoading] = useState(true);
    const { t, lang } = useLang();

    useEffect(() => {
        const fetchArticles = async () => {
            try {
                setLoading(true);
                const response = await get_articles(lang);
                if (response.ok) {
                    const data = await response.json();
                    setArticlesList(data);
                }
            } catch (err) {
                console.error("Failed to load articles", err);
            } finally {
                setLoading(false);    
            }
        };
        fetchArticles();
    }, [lang]);

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
                        {loading ? (
                            <div style={{marginTop: "20px"}}>{t("loading")}</div>
                        ) : articlesList.length > 0 ? (
                            articlesList.slice(0, 5).map((data, index) => (
                                <LinkArticleBtn
                                data={data}
                                key={index}
                                />
                            ))
                        ) : (
                            <div style={{marginTop: "20px"}}>{t("nothing_found")}</div>
                        )}
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