import { Link } from "react-router-dom";
import styles from "./Article.module.css";

const Article = ({data}) => {
    let imageUrl = data.image;
    if (!imageUrl && data.section === "products") {
        imageUrl = "https://www.doterra.com/medias/New-Default-Image.png?context=bWFzdGVyfHJvb3R8MjMzMzg0NHxpbWFnZS9wbmd8YzNsekxXMWhjM1JsY2k5eWIyOTBMMmhtTnk5b1ltUXZNamt6TWpZNU9Ua3lOVGN4TVRndlRtVjNMVVJsWm1GMWJIUXRTVzFoWjJVdWNHNW58M2Y5NzU2N2YyZDJhYjcyNDFhYzY5YWY2N2RjY2I5OTQ3MDBlNDQxMjUyOTNmZTNkOTdlMTc1MWQxNjY2Y2QxNA";
    }

    return (
        <Link 
            to={`/article/${data.slug}`} 
            style={{ textDecoration: 'none', display: 'block', width: '100%', boxSizing: 'border-box' }}
        >
            <div className={styles.wrapper}>
                {imageUrl && (
                    <div className={styles.imgWrap}>
                        <img
                            src={imageUrl}
                            alt={data.title}
                            className={styles.img}
                        />
                    </div>
                )}
                {!imageUrl && (
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