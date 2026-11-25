import { useEffect, useMemo, useState } from "react";

import styles from "./Home.module.css";
import { useLang } from "../../../contexts/LangContext";
import { ChatLinkBtn } from "./components/LinkBtn/posterity/ChatLinkBtn";
import { ArticlesLinkBtn } from "./components/LinkBtn/posterity/ArticlesLinkBtn";
import { LinkArticleBtn } from "./components/LinkArticleBtn";
import { TelegramLinkBtn } from "./components/LinkBtn/posterity/TelegramLinkBtn";
import { get_articles } from "../../../api/articles";
import { openExternalLink } from "../../../utils/openLink";

const SPECIALIST_TG_URL = "https://t.me/nkotelianska";
const POPULAR_SLUGS = [
    "lavender",
    "peppermint",
    "lemon",
    "frankincense",
    "doterra-on-guard",
    "on-guard",
    "deep-blue",
    "doterra-breathe",
    "tea-tree",
    "wild-orange",
];


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

    const popularArticles = useMemo(() => {
        if (!articlesList.length) return [];
        const bySlug = new Map(articlesList.map((a) => [a.slug, a]));
        const picked = [];
        for (const s of POPULAR_SLUGS) {
            if (bySlug.has(s) && picked.length < 6) {
                picked.push(bySlug.get(s));
            }
        }
        if (picked.length < 6) {
            const used = new Set(picked.map((a) => a.slug));
            for (const a of articlesList) {
                if (!used.has(a.slug) && a.image) {
                    picked.push(a);
                    used.add(a.slug);
                    if (picked.length >= 6) break;
                }
            }
        }
        return picked;
    }, [articlesList]);

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
                        ) : popularArticles.length > 0 ? (
                            popularArticles.map((data) => (
                                <LinkArticleBtn
                                data={data}
                                key={data.slug}
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
                <a
                    className={styles.contact}
                    href={SPECIALIST_TG_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => {
                        e.preventDefault();
                        openExternalLink(SPECIALIST_TG_URL);
                    }}
                >
                    {t("contact_specialist")}
                </a>
            </div>
        </>
    );
}

export {Home};