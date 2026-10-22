import { useState } from "react";
import { Link } from "react-router-dom";

import styles from "./LinkArticleBtn.module.css";

const LinkArticleBtn = ({data}) => {
    const [imgError, setImgError] = useState(false);
    const cleanTitle = (data.title || "").replace(/\s*\((?:чанк|chunk)\s*\d+\)/gi, "").trim();

    return (
        <>
            <Link to={`/article/${data.slug}`} className={styles.linkToBtn}>
                <div className={styles.wrapper}>
                    <div className={styles.img}>
                        {data.image && !imgError
                            ? <img src={data.image} alt={cleanTitle} onError={() => setImgError(true)} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '10px' }} />
                            : <span style={{ fontSize: '28px' }}>🌿</span>
                        }
                    </div>
                    <h3>{cleanTitle}</h3>
                </div>
            </Link>
        </>
    );
}

export {LinkArticleBtn};