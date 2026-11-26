import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import styles from "./ArticleView.module.css";
import { useLang } from "../../../contexts/LangContext";
import { openExternalLink } from "../../../utils/openLink";

import { get_article } from "../../../api/articles";


const ArticleView = () => {
    const { slug } = useParams();
    const navigate = useNavigate();
    const [articleData, setArticleData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const { t, lang } = useLang();

    useEffect(() => {
        const fetchArticle = async () => {
            try {
                setLoading(true);
                setError("");
                const response = await get_article(slug, lang);
                
                if (!response.ok) {
                    throw new Error("Не вдалося завантажити статтю");
                }
                const data = await response.json();
                setArticleData(data);
            } catch (err) {
                console.error(err);
                setError(t("article_error"));
            } finally {
                setLoading(false);
            }
        };

        fetchArticle();
    }, [slug, lang]);

    const handleContentClick = useCallback((event) => {
        const anchor = event.target?.closest?.("a");
        if (!anchor) return;
        const rawHref = (anchor.getAttribute("href") || "").trim();
        if (!rawHref) return;

        if (/^https?:\/\//i.test(rawHref) || rawHref.startsWith("mailto:")) {
            event.preventDefault();
            openExternalLink(rawHref);
            return;
        }

        // Внутрішні посилання між продуктами та книгами (напр. 01_oils_safety_reference, lavender-touch)
        event.preventDefault();
        const cleaned = rawHref
            .replace(/^#?\/?article\//i, "")
            .replace(/\.md$/i, "")
            .replace(/^\/+/, "")
            .replace(/_/g, "-")
            .trim();
        if (cleaned) {
            navigate(`/article/${cleaned}`);
        }
    }, [navigate]);

    return (
        <div className={styles.wrapper}>
            <div className={styles.header}>
                <button
                    className={styles.backBtn}
                    onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/articles"))}
                >
                    {t("article_back")}
                </button>
            </div>
            
            {loading && <div className={styles.loading}>{t("loading")}</div>}
            
            {error && <div className={styles.error}>{error}</div>}
            
            {articleData && (
                <div className={styles.content}>
                    <div 
                        className={styles.markdownContent}
                        onClick={handleContentClick}
                        dangerouslySetInnerHTML={{ __html: articleData.content }} 
                    />
                </div>
            )}
        </div>
    );
}

export { ArticleView };
