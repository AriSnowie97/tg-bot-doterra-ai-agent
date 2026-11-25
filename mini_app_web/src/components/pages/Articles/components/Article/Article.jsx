import { useState } from "react";
import { Link } from "react-router-dom";
import styles from "./Article.module.css";

const Article = ({data}) => {
    const [imgError, setImgError] = useState(false);

    let imageUrl = data.image;
    if (imageUrl && imageUrl.includes("New-Default-Image")) {
        imageUrl = "";
    }

    const cleanTitle = (data.title || "").replace(/\s*\((?:чанк|chunk)\s*\d+\)/gi, "").trim();

    return (
        <Link 
            to={`/article/${data.slug}`} 
            style={{ textDecoration: 'none', display: 'block', width: '100%', boxSizing: 'border-box' }}
        >
            <div className={styles.wrapper}>
                {imageUrl && !imgError ? (
                    <div className={styles.imgWrap}>
                        <img
                            src={imageUrl}
                            alt={cleanTitle}
                            className={styles.img}
                            onError={() => setImgError(true)}
                        />
                    </div>
                ) : (
                    <div className={styles.imgPlaceholder}>🌿</div>
                )}
                <div className={styles.description}>
                    <h3>{cleanTitle}</h3>
                    <span>{data.short}</span>
                    {data.tag && (
                        <div className={styles.tag}>
                            <p>#{data.tag}</p>
                        </div>
                    )}
                </div>
            </div>
        </Link>
    );
}

export {Article};