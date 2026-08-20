import { useState, useEffect, useMemo } from "react";
import { useLang } from "../../../contexts/LangContext";

import styles from "./Articles.module.css";
import { Article } from "./components/Article";

const Articles = () => {
    const [search, setSearch] = useState("");
    const [articlesList, setArticlesList] = useState([]);
    const [loading, setLoading] = useState(true);
    const [activeTag, setActiveTag] = useState("Усі");
    const { t } = useLang();

    useEffect(() => {
        const fetchArticles = async () => {
            try {
                setLoading(true);
                const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const response = await fetch(`${API_URL}/api/articles`);
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

    // Отримуємо унікальні категорії
    const categories = useMemo(() => {
        const tags = new Set(articlesList.map(a => a.tag).filter(Boolean));
        return ["Усі", ...Array.from(tags).sort()];
    }, [articlesList]);

    // Фільтруємо за категорією та пошуком
    const filteredArticles = useMemo(() => {
        return articlesList.filter(data => {
            const matchTag = activeTag === "Усі" || data.tag === activeTag;
            const matchSearch = search === "" || 
                (data.title && data.title.toLowerCase().includes(search.toLowerCase())) ||
                (data.short && data.short.toLowerCase().includes(search.toLowerCase()));
            return matchTag && matchSearch;
        });
    }, [articlesList, activeTag, search]);

    return (
        <div className={styles.wrapper}>
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