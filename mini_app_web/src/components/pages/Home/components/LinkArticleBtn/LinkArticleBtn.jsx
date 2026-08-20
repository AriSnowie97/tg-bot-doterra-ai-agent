import { Link } from "react-router-dom";

import styles from "./LinkArticleBtn.module.css";

const LinkArticleBtn = ({data}) => {
    return (
        <>
            <Link to={`/article/${data.slug}`} className={styles.linkToBtn}>
                <div className={styles.wrapper}>
                    <div className={styles.img}>
                        {data.image
                            ? <img src={data.image} alt={data.title} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '10px' }} />
                            : <span style={{ fontSize: '28px' }}>🌿</span>
                        }
                    </div>
                    <h3>{data.title}</h3>
                </div>
            </Link>
        </>
    );
}

export {LinkArticleBtn};