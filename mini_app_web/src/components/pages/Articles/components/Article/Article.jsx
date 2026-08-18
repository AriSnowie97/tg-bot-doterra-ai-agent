import { Link } from "react-router-dom";

import styles from "./Article.module.css";


const Article = ({data}) => {
    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.img}>Prod Img</div>
                <div className={styles.description}>
                    <h3>{data.title}</h3>
                    <span>{data.short}</span>
                    <div className={styles.tag}>
                        <p>#{data.tag}</p>
                    </div>
                </div>
            </div>
        </>
    );
}

export {Article};