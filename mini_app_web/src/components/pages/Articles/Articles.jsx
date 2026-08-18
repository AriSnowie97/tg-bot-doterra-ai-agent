import { useState, useEffect } from "react";

import styles from "./Articles.module.css";
import { Article } from "./components/Article";

import { articles } from "../../../dataMocks";


const Articles = () => {
    const [search, setSearch] = useState("");
    const [articlesList, setArticlesList] = useState(articles)

    useEffect(() => {
        if (search=="") {
            setArticlesList(articles);
        } else {
            setArticlesList([]);

            articles.forEach(data => {
                if (data.title.toLowerCase().includes(search.toLowerCase())
                    || data.short.toLowerCase().includes(search.toLowerCase())) {

                    setArticlesList(prev => [
                        ...prev,
                        data
                    ]);
                }
            });
        }
    }, [search]);


    return (
        <>
            <div className={styles.wrapper}>
                <input
                className={styles.input}
                type="text"
                name="search"
                value={search}
                onChange={(event) => setSearch(`${event.target.value}`)}
                placeholder="Пошук статей..."
                />
                <div className={styles.slider}>
                    <div className={styles.articles}>
                        {articlesList.map((data, index) => (
                            <Article
                            data={data}
                            key={index}
                            />
                        ))}
                    </div>
                </div>
            </div>
        </>
    );
}

export {Articles};