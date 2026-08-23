import { useState, useEffect, useMemo } from "react";
import { useLang } from "../../../contexts/LangContext";

import styles from "./Articles.module.css";
import { Article } from "./components/Article";

import { get_articles } from "../../../api/articles";

import { ArticlesSvg, SunSvg, ChatSvg, GlobeSvg, ContactsSvg } from "../../../assets/icons";

const SECTION_DATA = {
    "products": { name: "Продукти", desc: "Ефірні олії, суміші та догляд", icon: ArticlesSvg },
    "symphony_of_the_cells": { name: "Симфонія клітин", desc: "Протоколи нанесення ефірних олій", icon: SunSvg },
    "advice": { name: "Поради", desc: "Рекомендації та корисні статті", icon: ChatSvg },
    "kits": { name: "Набори", desc: "Стартові та подарункові набори", icon: GlobeSvg },
    "docs": { name: "Довідники", desc: "Технічна інформація та гайди", icon: ContactsSvg }
};

const Articles = () => {
    const [search, setSearch] = useState("");
    const [articlesList, setArticlesList] = useState([]);
    const [loading, setLoading] = useState(true);
    const [activeTag, setActiveTag] = useState("Усі");
    const [activeSection, setActiveSection] = useState(null);
    const { t } = useLang();

    useEffect(() => {
        const fetchArticles = async () => {
            try {
                setLoading(true);
                const response = await get_articles();
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
                {loading ? (
                    <div style={{marginTop: "20px"}}>Завантаження...</div>
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
                ← Назад до розділів
            </button>
            <input
                className={styles.input}
                type="text"
                name="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Пошук статей..."
            />
            
            {!loading && categories.length > 1 && (
                <div className={styles.tagsContainer}>
                    {categories.map(tag => (
                        <button 
                            key={tag}
                            className={`${styles.tagBtn} ${activeTag === tag ? styles.activeTag : ""}`}
                            onClick={() => setActiveTag(tag)}
                        >
                            {tag}
                        </button>
                    ))}
                </div>
            )}

            <div className={styles.slider}>
                <div className={styles.articles}>
                    {loading ? (
                        <div style={{marginTop: "20px"}}>Завантаження...</div>
                    ) : filteredArticles.length > 0 ? (
                        filteredArticles.map((data, index) => (
                            <Article data={data} key={index} />
                        ))
                    ) : (
                        <div style={{marginTop: "20px"}}>Нічого не знайдено</div>
                    )}
                </div>
            </div>
        </div>
    );
}

export {Articles};