import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import styles from "./ArticleView.module.css";

const ArticleView = () => {
    const { slug } = useParams();
    const navigate = useNavigate();
    const [articleData, setArticleData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const fetchArticle = async () => {
            try {
                setLoading(true);
                const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const response = await fetch(`${API_URL}/api/docs/${slug}`);
                if (!response.ok) {
                    throw new Error("Не вдалося завантажити статтю");
                }
                const data = await response.json();
                setArticleData(data);
            } catch (err) {
                console.error(err);
                setError("Помилка підключення до бази знань. Переконайтеся, що бекенд запущено.");
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
                    ← Назад
                </button>
            </div>
            
            {loading && <div className={styles.loading}>Завантаження...</div>}
            
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
