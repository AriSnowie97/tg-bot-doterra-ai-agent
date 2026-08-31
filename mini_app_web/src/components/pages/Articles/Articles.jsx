import { useState, useEffect, useMemo } from "react";
import { useLang } from "../../../contexts/LangContext";

import styles from "./Articles.module.css";
import { Article } from "./components/Article";
import { get_articles } from "../../../api/articles";
import { ArticlesSvg, SunSvg, ChatSvg, GlobeSvg, ContactsSvg } from "../../../assets/icons";


const Articles = () => {
    const [search, setSearch] = useState("");
    const [articlesList, setArticlesList] = useState([]);
    const [loading, setLoading] = useState(true);
    const [activeTag, setActiveTag] = useState("Усі");
    const [activeSection, setActiveSection] = useState(null);
    const { t, lang } = useLang();
    const SECTION_DATA = {
        "products": { icon: ArticlesSvg },
        "symphony_of_the_cells": { icon: SunSvg },
        "advice": { icon: ChatSvg },
        "kits": { icon: GlobeSvg },
        "docs": { icon: ContactsSvg }
    };

    // Adding text to sections
    Object.entries(SECTION_DATA).map(([key, data]) => {
        data.name = t("articles_section_data")?.[key]?.name ?? "name";
        data.desc = t("articles_section_data")?.[key]?.description ?? "description";
    });
    
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
    }, []);

    useEffect(() => {
        if (lang === "ua") {
            console.log("Привіт");
        } else {
            console.log("Hello");
        }
        console.log(lang);

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

    const sectionArticles = useMemo(() => {
        if (!activeSection) return [];
        return articlesList.filter(a => a.section === activeSection);
    }, [articlesList, activeSection]);

    // Отримуємо унікальні категорії
    const categories = useMemo(() => {
        const tags = new Set(sectionArticles.map(a => a.tag).filter(Boolean));
        return ["Усі", ...Array.from(tags).sort()];
    }, [sectionArticles]);

    // Фільтруємо за категорією та пошуком
    const filteredArticles = useMemo(() => {
        return sectionArticles.filter(data => {
            const matchTag = activeTag === "Усі" || data.tag === activeTag;
            const matchSearch = search === "" || 
                (data.title && data.title.toLowerCase().includes(search.toLowerCase())) ||
                (data.short && data.short.toLowerCase().includes(search.toLowerCase()));
            return matchTag && matchSearch;
        });
    }, [sectionArticles, activeTag, search]);

    const handleSectionClick = (key) => {
        setActiveSection(key);
        setActiveTag("Усі");
        setSearch("");
    };

    if (activeSection === null) {
        return (
            <div className={styles.wrapper}>
                <h1 className={styles.pageTitle}>{t("articles")}</h1>
                {loading ? (
                    <div style={{marginTop: "20px"}}>{t("loading")}</div>
                ) : (
                    <div className={styles.sectionsContainer}>
                        {Object.entries(SECTION_DATA).map(([key, data]) => {
                            const count = articlesList.filter(a => a.section === key).length;
                            if (count === 0) return null;
                            const SvgIcon = data.icon;
                            return (
                                <button key={key} className={styles.sectionBtn} onClick={() => handleSectionClick(key)}>
                                    <div className={styles.sectionImg}>
                                        <SvgIcon className={styles.Svg} />
                                    </div>
                                    <div className={styles.sectionText}>
                                        <h3>{data.name}</h3>
                                        <p>{data.desc} ({count})</p>
                                    </div>
                                    <div className={styles.sectionArrow}>
                                        <p>→</p>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className={styles.wrapper}>
            <button className={styles.backBtn} onClick={() => setActiveSection(null)}>
                {t("articles_back")}
            </button>
            <input
                className={styles.input}
                type="text"
                name="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t("articles_search_placeholder")}
            />
            
            {!loading && categories.length > 1 && (
                <div className={styles.tagsContainer}>
                    {categories.map(tag => (
                        <button 
                            key={tag}
                            className={`${styles.tagBtn} ${activeTag === tag ? styles.activeTag : ""}`}
                            onClick={() => setActiveTag(tag)}
                        >
                            {tag === "Усі" ? t("articles_category_all") : tag}
                        </button>
                    ))}
                </div>
            )}

            <div className={styles.slider}>
                <div className={styles.articles}>
                    {loading ? (
                        <div style={{marginTop: "20px"}}>{t("loading")}</div>
                    ) : filteredArticles.length > 0 ? (
                        filteredArticles.map((data, index) => (
                            <Article data={data} key={index} />
                        ))
                    ) : (
                        <div style={{marginTop: "20px"}}>{t("nothing_found")}</div>
                    )}
                </div>
            </div>
        </div>
    );
}

export {Articles};