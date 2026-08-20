import { Link } from "react-router-dom";

import styles from "./Article.module.css";


const Article = ({data}) => {
    return (
        <Link 
            to={`/article/${data.slug}`} 
            style={{ textDecoration: 'none', display: 'block', width: '100%', boxSizing: 'border-box' }}
        >
            <div className={styles.wrapper}>
                {data.image && (
                    <div className={styles.imgWrap}>
                        <img
                            src={data.image}
                            alt={data.title}
                            className={styles.img}
                        />
                    </div>
                )}
                {!data.image && (
                    <div className={styles.imgPlaceholder}>🌿</div>
                )}
                <div className={styles.description}>
                    <h3>{data.title}</h3>
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