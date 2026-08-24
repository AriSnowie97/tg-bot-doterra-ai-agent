import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import styles from "./ArticleView.module.css";
import { useLang } from "../../../contexts/LangContext";

import { get_article } from "../../../api/articles";


const ArticleView = () => {
    const { slug } = useParams();
    const navigate = useNavigate();
    const [articleData, setArticleData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const { t } = useLang();

    useEffect(() => {
        const fetchArticle = async () => {
            try {
                setLoading(true);
                const response = await get_article(slug);
                
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
    }, [slug]);

    return (
        <div className={styles.wrapper}>
            <div className={styles.header}>
                <button className={styles.backBtn} onClick={() => navigate(-1)}>
                    {t("article_back")}
                </button>
            </div>
            
            {loading && <div className={styles.loading}>{t("loading")}</div>}
            
            {error && <div className={styles.error}>{error}</div>}
            
            {articleData && (
                <div className={styles.content}>
                    <div 
                        className={styles.markdownContent}
                        dangerouslySetInnerHTML={{ __html: articleData.content }} 
                    />
                </div>
            )}
        </div>
    );
}

export { ArticleView };
